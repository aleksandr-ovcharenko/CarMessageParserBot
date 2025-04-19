import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")

ALLOWED_USERS = [1873460275]  # список user_id

ENDPOINT_URL = os.getenv("ENDPOINT_URL", "http://localhost:5000/api/import_car")
API_TOKEN = os.getenv("API_TOKEN", "your-secret-token")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 30))