import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from lib.avatar import validate_avatar
from lib.config import GENAI_API_KEY, GENAI_MODEL


def generate_avatar(description):
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
        "Return JSON with a rows field containing exactly 16 strings of exactly 16 characters; "
        "each character must be a digit from 0 through 7. Do not include any other content.\n"
        f"Character description: {description}"
    )
    request_body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseFormat": {
                "text": {
                    "mimeType": "APPLICATION_JSON",
                    "schema": {
                        "type": "OBJECT",
                        "properties": {
                            "rows": {
                                "type": "ARRAY",
                                "minItems": 16,
                                "maxItems": 16,
                                "items": {
                                    "type": "STRING",
                                    "minLength": 16,
                                    "maxLength": 16,
                                    "pattern": "^[0-7]{16}$",
                                },
                            }
                        },
                        "required": ["rows"],
                    }
                }
            },
            "maxOutputTokens": 400,
        },
    }
    request = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(GENAI_MODEL, safe='')}:generateContent",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GENAI_API_KEY.strip(),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"Gemini API error ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Gemini API: {exc.reason}") from exc

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return validate_avatar(json.loads(text)["rows"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini returned an invalid avatar grid.") from exc