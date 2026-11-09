from google import genai
from groq import Groq, APIError, APIConnectionError

from lib.avatar import validate_avatar
from lib.config import (
    GENAI_API_KEY, 
    GENAI_MODEL, 
    GROQ_API_KEY,      # Make sure to define these in your config
    GROQ_MODEL         # e.g., "llama-3.3-70b-versatile" or similar fast model
)


def generate_avatar(description):
    if not isinstance(description, str):
        raise ValueError("Character description must be text.")
    description = description.strip()
    if not description:
        raise ValueError("Describe the character first.")
    if len(description) > 240:
        raise ValueError("Character descriptions must be 240 characters or fewer.")

    prompt = (
        "Design a clean, readable pixel-art game avatar from the character description below. "
        "The final sprite is 16 by 16 pixels and will be enlarged to 32 by 32 using nearest-neighbor scaling. "
        "Use only these palette indexes: 0 transparent, 1 dark outline, 2 skin, 3 skin shadow, "
        "4 clothing, 5 accent, 6 highlight, 7 off-white. "
        "Create one centered, front-facing character with a simple silhouette and clear face. "
        "Use index 0 for background and keep the sprite inside the canvas. "
        "Return exactly 16 lines of exactly 16 characters each, separated by newline characters. "
        "Each character must be a digit from 0 through 7. Do not include any other content.\n\n"
        f"Character description: {description}"
    )

    text = None

    # --- 1. Try Primary API (Google GenAI) ---
    if GENAI_API_KEY and GENAI_API_KEY.strip():
        try:
            client = genai.Client(api_key=GENAI_API_KEY.strip())
            response = client.models.generate_content(
                model=GENAI_MODEL,
                contents=prompt,
            )
            text = response.text
        except Exception as e:
            print(f"Primary API (Gemini) failed: {e}. Switching to Groq fallback...")

    # --- 2. Fallback to Secondary API (Groq) if Gemini failed or wasn't configured ---
    if not text or not text.strip():
        if not GROQ_API_KEY or not GROQ_API_KEY.strip():
            raise RuntimeError("AI avatar generation failed on primary API and Groq fallback is not configured.")
        
        try:
            groq_client = Groq(api_key=GROQ_API_KEY.strip())
            completion = groq_client.chat.completions.create(
                model=GROQ_MODEL,  # e.g., "llama-3.3-70b-versatile"
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.7, # Lower temperature helps keep format strict
            )
            text = completion.choices[0].message.content
        except (APIError, APIConnectionError, Exception) as groq_err:
            raise RuntimeError(f"Both primary and fallback AI providers failed. Groq error: {groq_err}")

    # --- 3. Validate Output ---
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("AI returned no avatar data. Try again.")

    try:
        return validate_avatar(text.strip().splitlines())
    except ValueError as exc:
        raise RuntimeError(f"AI returned an invalid pixel grid: {exc}") from exc