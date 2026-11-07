import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def test_gemini():
    # Pass the key explicitly from the environment variable
    client = genai.Client(api_key=os.getenv("GENAI_API_KEY"))
    
    print("Sending prompt to Gemini...")
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="""Design a clean, readable pixel-art game avatar from the character description below. The final sprite is 16 by 16 pixels and will be enlarged to 32 by 32 using nearest-neighbor scaling. Use only these palette indexes: 0 transparent, 1 dark outline, 2 skin, 3 skin shadow, 4 clothing, 5 accent, 6 highlight, 7 off-white. Create one centered, front-facing character with a simple silhouette and clear face. Use index 0 for background and keep the sprite inside the canvas. Return string with every row represented by a line of exactly 16 characters lines are separated with backslash n; each character must be a digit from 0 through 7. Do not include any other content.\n

character descripting: a cute yellow round figure with red eyes""",
    )
    
    print("\n--- Response from Gemini ---")
    print(response.text)

if __name__ == "__main__":
    test_gemini()