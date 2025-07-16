import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from config.logger import logger
from app.db.user_data import get_user_summary, get_user_profile

# Load environment variables
load_dotenv()

print("MY OPENAI KEY =", os.getenv("AI_API_KEY"))

# Load the system prompt from file
try:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
    logger.info("System prompt loaded successfully.")
except FileNotFoundError as e:
    logger.error(f"System prompt file not found: {e}")
    raise FileNotFoundError("The system prompt file (app/ai/prompt.txt) is missing.")

# Load AI config
api_key = os.getenv("AI_API_KEY")
provider = os.getenv("AI_PROVIDER", "openai")
model_name = os.getenv("AI_MODEL", "gpt-4o")

if not api_key:
    logger.error("AI_API_KEY is missing from environment variables.")
    raise ValueError("AI_API_KEY is required.")

# Initialize client
if provider == "openai":
    ai_client = OpenAI(api_key=api_key)
elif provider == "anthropic":
    from anthropic import Anthropic
    ai_client = Anthropic(api_key=api_key)
else:
    raise ValueError(f"Unsupported AI provider: {provider}")


# Unified function
async def ask_ai(
    user_id: int,
    message_history: list,
    pending_messages_text: str = None
) -> dict:
    logger.info(f"Sending message history to AI for user {user_id} with {len(message_history)} messages.")

    try:
        user_summary = get_user_summary(user_id)
        user_profile = get_user_profile(user_id)

        # Combine system prompt with context
        full_prompt = system_prompt
        if user_summary:
            full_prompt += f"\n\n# USER SUMMARY:\n{user_summary}"
        if user_profile:
            full_prompt += f"\n\n# USER PROFILE:\n{json.dumps(user_profile, ensure_ascii=False, indent=2)}"

        # Build messages list
        messages = []
        messages.append({"role": "system", "content": full_prompt})

        # If there are pending messages, inform the AI
        if pending_messages_text:
            messages.append({
                "role": "user",
                "content": pending_messages_text
            })

        # Add actual chat history
        messages.extend(message_history)

        # Call the chosen model
        if provider == "openai":
            response = ai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=2048,
            )
            full_text = response.choices[0].message.content or ""
        elif provider == "anthropic":
            response = ai_client.messages.create(
                model=model_name,
                system=full_prompt,
                messages=message_history,
                max_tokens=2048,
                stream=False,
            )
            full_text = response.content[0].text or ""
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        # Check if a PDF should be generated
        pdf_flag = "[SEND_PDF]" in full_text
        clean_text = full_text.replace("[SEND_PDF]", "").strip()

        # Attempt to extract JSON from the message
        pdf_content = None
        profile_updates = None
        try:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1:
                json_blob = clean_text[start:end + 1]
                parsed = json.loads(json_blob)
                if isinstance(parsed, dict):
                    pdf_content = parsed
                    profile_updates = parsed.get("profile_updates")
                clean_text = clean_text[:start].strip()
        except Exception as e:
            logger.warning(f"Failed to parse JSON content: {e}")

        return {
            "reply": clean_text,
            "pdf_request": pdf_flag,
            "pdf_content": pdf_content,
            "profile_updates": profile_updates,
        }

    except Exception as e:
        logger.error(f"Error communicating with AI model: {e}")
        return {
            "reply": "عذرًا، حدث خطأ أثناء محاولة الرد من الذكاء الاصطناعي.",
            "pdf_request": False,
            "pdf_content": None,
            "profile_updates": None,
        }
