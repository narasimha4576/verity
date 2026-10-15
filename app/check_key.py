import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL")
if not key or not model:
    raise SystemExit("Fill GEMINI_API_KEY and GEMINI_MODEL in .env")

client = genai.Client(api_key=key)
reply = client.models.generate_content(model=model, contents="Reply with the single word: ready")
print(reply.text)
