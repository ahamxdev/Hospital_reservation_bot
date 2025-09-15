# bot_config.py
# Read Telegram token securely from .env file
import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

# دریافت توکن بات
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Telegram bot token not found. Set BOT_TOKEN in .env file."
    )
