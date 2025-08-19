# facebook_business_bot/main.py
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, ConversationHandler, CallbackQueryHandler
from telegram import Update

from config import TELEGRAM_BOT_TOKEN, ADMIN_ID
from database.db_manager import db_manager
from telegram_bot.handlers import start_command, handle_cookies_message, help_command, status_command, handle_callback_query # Import handle_callback_query
from telegram_bot.admin_handlers import (
    admin_menu_command, list_users_command, # These remain CommandHandlers
    admin_add_user_start, add_user_get_id, add_user_get_api_key, add_user_get_sub_days, 
    ADD_USER_STATE_ID, ADD_USER_STATE_API_KEY, ADD_USER_STATE_SUB_DAYS,
    admin_delete_user_start, delete_user_get_id, DELETE_USER_STATE_ID,
    admin_send_message_to_all_start, send_message_to_all_get_message, SEND_MESSAGE_STATE,
    admin_reward_users_start, reward_users_get_days, REWARD_USERS_STATE_DAYS, # Corrected state name
    admin_renew_user_subscription_start, renew_user_get_id, renew_user_get_days, 
    RENEW_USER_STATE_ID, RENEW_USER_STATE_DAYS,
    cancel_admin_conversation # For cancelling conversations
)
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

    escaped_error_message = escape_markdown(str(context.error), version=2)
    
    message = (
        "An unexpected error occurred while processing your request\\. "
        "The developers have been notified\\.\n\n"
        f"Error: `{escaped_error_message}`"
    )
    
    if update and update.effective_message:  # تحقق من وجود update
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

    # --- Admin Command Handlers (single-step) ---
    application.add_handler(CommandHandler("admin", admin_menu_command))
    application.add_handler(CommandHandler("list_users", list_users_command)) # This remains a simple command

    # --- Admin Conversation Handlers ---

    # Add User Conversation
    add_user_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_user_start, pattern='^admin_add_user_start$')],
        states={
            ADD_USER_STATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_get_id)],
            ADD_USER_STATE_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_get_api_key)],
            ADD_USER_STATE_SUB_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_get_sub_days)],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_conversation)],
        allow_reentry=True # Allow restarting conversation if already in one
    )
    application.add_handler(add_user_conv_handler)

    # Delete User Conversation
    delete_user_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_delete_user_start, pattern='^admin_delete_user_start$')],
        states={
            DELETE_USER_STATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user_get_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_conversation)],
        allow_reentry=True
    )
    application.add_handler(delete_user_conv_handler)

    # Send Message to All Conversation
    send_message_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_send_message_to_all_start, pattern='^admin_send_message_to_all_start$')],
        states={
            SEND_MESSAGE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_to_all_get_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_conversation)],
        allow_reentry=True
    )
    application.add_handler(send_message_conv_handler)

    # Reward Users Conversation (for all users)
    reward_users_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_reward_users_start, pattern='^admin_reward_users_start$')],
        states={
            REWARD_USERS_STATE_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reward_users_get_days)],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_conversation)],
        allow_reentry=True
    )
    application.add_handler(reward_users_conv_handler)

    # Renew User Subscription Conversation (for specific user)
    renew_user_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_renew_user_subscription_start, pattern='^admin_renew_user_subscription_start$')],
        states={
            RENEW_USER_STATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_user_get_id)],
            RENEW_USER_STATE_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, renew_user_get_days)],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_conversation)],
        allow_reentry=True
    )
    application.add_handler(renew_user_conv_handler)

    # --- General Callback Query Handler (for user-facing buttons like start/stop creation) ---
    application.add_handler(CallbackQueryHandler(handle_callback_query)) 

    # --- Message Handler for Cookies (any text message that is not a command or part of a conversation) ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookies_message))

    # --- Register error handler ---
    application.add_error_handler(error_handler) 

    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

