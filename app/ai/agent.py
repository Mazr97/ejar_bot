import os
import json
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from config.logger import logger
from app.db.user_data import get_user_summary, get_user_profile

# ── Load environment ───────────────────────────────────────────────────────────
load_dotenv()
api_key    = os.getenv("AI_API_KEY")
model_name = "gpt-4o"
if not api_key:
    logger.error("❌ AI_API_KEY is missing in environment variables.")
    raise ValueError("AI_API_KEY is required in .env")
ai_client = OpenAI(api_key=api_key)

# ── Load system prompt ─────────────────────────────────────────────────────────
prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
try:
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
    logger.info("✅ System prompt loaded.")
except FileNotFoundError as e:
    logger.error(f"❌ System prompt file not found: {e}")
    raise FileNotFoundError("The system prompt file (prompt.txt) is missing.")

# ── Async AI caller with streaming ─────────────────────────────────────────────
async def ask_ai(
    user_id: int,
    message_history: list,
    pending_messages_text: str = None
) -> dict:
    logger.info(f"🤖 ask_ai → user {user_id}, history length={len(message_history)}")
    try:
        # Fetch summary/profile
        user_summary = get_user_summary(user_id) or ""
        user_profile = get_user_profile(user_id) or {}

        # Build system prompt
        full_prompt = system_prompt
        if user_summary:
            full_prompt += f"\n\n# USER SUMMARY:\n{user_summary}"
        if user_profile:
            profile_json = json.dumps(user_profile, ensure_ascii=False, indent=2)
            full_prompt += f"\n\n# USER PROFILE:\n{profile_json}"

        # Trim history to last N messages
        MAX_HISTORY = 20
        trimmed = message_history[-MAX_HISTORY:] if len(message_history) > MAX_HISTORY else message_history

        # Compose messages
        messages = [{"role": "system", "content": full_prompt}]
        if pending_messages_text:
            messages.append({"role": "user", "content": pending_messages_text})
        messages.extend(trimmed)

        # Streaming completion
        stream = ai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            max_tokens=1024,
        )

        raw_chunks = []
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                raw_chunks.append(delta)

        raw = "".join(raw_chunks)
        logger.debug(f"AI raw preview: {raw[:200]!r}")

        # Handle [SEND_PDF] tag + embedded JSON
        pdf_flag   = "[SEND_PDF]" in raw
        clean_text = raw.replace("[SEND_PDF]", "").strip()

        pdf_content     = None
        profile_updates = None
        start = clean_text.find("{")
        end   = clean_text.rfind("}")
        if start != -1 and end != -1:
            try:
                blob   = clean_text[start : end + 1]
                parsed = json.loads(blob)
                if isinstance(parsed, dict):
                    pdf_content     = parsed
                    profile_updates = parsed.get("profile_updates")
                clean_text = clean_text[:start].strip()
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse JSON blob: {e}")

        return {
            "reply":           clean_text,
            "pdf_request":     pdf_flag,
            "pdf_content":     pdf_content,
            "profile_updates": profile_updates,
        }

    except Exception as e:
        logger.error(f"❌ OpenAI error for user {user_id}: {e}")
        return {
            "reply":           "عذرًا، حدث خطأ أثناء محاولة الرد من الذكاء الاصطناعي.",
            "pdf_request":     False,
            "pdf_content":     None,
            "profile_updates": None,
        }

# ── Sync wrapper for run_in_executor ─────────────────────────────────────────
def ask_ai_sync(
    user_id: int,
    message_history: list,
    pending_messages_text: str = None
) -> dict:
    """
    Synchronous wrapper around ask_ai(), safe to call in a threadpool.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            ask_ai(user_id, message_history, pending_messages_text)
        )
    finally:
        loop.close()
