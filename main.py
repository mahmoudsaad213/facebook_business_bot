# facebook_business_bot/main.py
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram import Update

from config import TELEGRAM_BOT_TOKEN, ADMIN_ID
from database.db_manager import db_manager
from telegram_bot.handlers import start_command, handle_cookies_message, help_command, status_command
from telegram_bot.admin_handlers import admin_menu_command, add_user_command, delete_user_command, list_users_command, send_message_to_all_command, reward_users_command, renew_user_subscription_command
import traceback

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    tb_string = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    logger.error(f"Full traceback:\n{tb_string}")

    # Escape markdown for the error message
    from utils.helpers import escape_markdown_v2
    escaped_error_message = escape_markdown_v2(str(context.error))
    
    message = (
        "An unexpected error occurred while processing your request\\. "
        "The developers have been notified\\.\n\n"
        f"Error: `{escaped_error_message}`"
    )
    
    if update.effective_message:
        await update.effective_message.reply_text(message, parse_mode='MarkdownV2')
    else:
        logger.warning("Error handler called without an effective message.")

def main():
    """Starts the Telegram bot."""
    logger.info("Starting Telegram Bot...")

    # Initialize DB Manager and ensure tables are created
    try:
        db_manager.create_tables()
        # Add admin user if not exists
        admin_user = db_manager.get_user(ADMIN_ID)
        if not admin_user:
            db_manager.add_user(ADMIN_ID, is_admin=True, subscription_days=3650) # Admin has long subscription
            logger.info(f"Admin user {ADMIN_ID} added.")
        else:
            logger.info(f"Admin user {ADMIN_ID} already exists.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        exit(1)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- User Command Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))

    # --- Admin Command Handlers ---
    application.add_handler(CommandHandler("admin", admin_menu_command))
    application.add_handler(CommandHandler("add_user", add_user_command))
    application.add_handler(CommandHandler("delete_user", delete_user_command))
    application.add_handler(CommandHandler("list_users", list_users_command))
    application.add_handler(CommandHandler("send_message_to_all", send_message_to_all_command))
    application.add_handler(CommandHandler("reward_users", reward_users_command))
    application.add_handler(CommandHandler("renew_user_subscription", renew_user_subscription_command))


    # --- Message Handler for Cookies (any text message that is not a command) ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookies_message))

    # --- Register error handler ---
    application.add_error_handler(error_handler) 

    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

