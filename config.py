# facebook_business_bot/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5895491379"))

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# TempMail API Configuration
TEMPMAIL_BASE_URL = "https://api.tempmail.co/v1"

# Business Creation Settings
MAX_RETRIES_PER_BUSINESS = 3
INITIAL_RETRY_DELAY = 5  # seconds
MAX_BUSINESSES_PER_SESSION = 50  # Maximum businesses to create in one session

# Validate required environment variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")
