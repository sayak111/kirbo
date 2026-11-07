from google import genai

from lib.avatar import validate_avatar
from lib.config import GENAI_API_KEY, GENAI_MODEL


def generate_avatar(description):
    if not isinstance(description, str):
        raise ValueError("Character description must be text.")
    description = description.strip()
    if not description:
        raise ValueError("Describe the character first.")
    if len(description) > 240:
        raise ValueError("Character descriptions must be 240 characters or fewer.")
    if not GENAI_API_KEY.strip():
        raise RuntimeError("AI avatar generation is not configured on the server.")

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

    client = genai.Client(api_key=GENAI_API_KEY.strip())
    response = client.models.generate_content(
        model=GENAI_MODEL,
        contents=prompt,
    )
    text = response.text
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Gemini returned no avatar data. Try again.")

    try:
        return validate_avatar(text.strip().splitlines())
    except ValueError as exc:
        raise RuntimeError(f"Gemini returned an invalid pixel grid: {exc}") from exc
