import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_BIND_HOST = os.getenv("SERVER_BIND_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "3000"))
GENAI_API_KEY = os.getenv("GENAI_API_KEY", "")