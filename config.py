# facebook_business_bot/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # Default to 0 if not set, ensure it's an integer

# --- TempMail API Configuration ---
TEMPMAIL_BASE_URL = "https://api.tempmail.co/v1"
# TEMPMAIL_API_TOKEN will be fetched per user from DB, not global here

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL") # e.g., "postgresql://user:password@host:port/dbname"

# --- Other Configurations ---
BUSINESS_CREATION_TIMEOUT = int(os.getenv("BUSINESS_CREATION_TIMEOUT", "300")) # seconds for waiting for email
MAX_RETRIES_PER_BUSINESS = int(os.getenv("MAX_RETRIES_PER_BUSINESS", "3"))
INITIAL_RETRY_DELAY = int(os.getenv("INITIAL_RETRY_DELAY", "5")) # seconds

# Basic validation
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables.")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables.")
if not ADMIN_ID:
    print("WARNING: ADMIN_ID is not set. Admin features will not be available.")

