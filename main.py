# facebook_business_bot/main.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram_bot.handlers import handle_cookies_message, create_business_loop, start_command, help_command, error_handler
from database.db_manager import DBManager as db_manager
# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database manager
db_manager = DBManager()

def main():
    """Starts the Telegram bot."""
    logger.info("Starting Telegram Bot...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Message handler for cookies (any text message that is not a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookies_message))

    # Register error handler
    application.add_error_handler(error_handler) 

    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
