# facebook_business_bot/telegram_bot/handlers.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.facebook_creator import create_facebook_business
from database.db_manager import db_manager

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and prompts for cookies."""
    await update.message.reply_text(
        "Welcome to the Facebook Business Creator Bot!\n"
        "To get started, please send your Facebook cookies as a single line of text.\n"
        "Example: `datr=...; sb=...; c_user=...; xs=...;`"
    )

async def handle_cookies_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, expecting them to be cookies."""
    user_id = update.effective_user.id
    cookies_input_str = update.message.text.strip()

    if cookies_input_str:
        try:
            parsed_cookies = parse_cookies(cookies_input_str)
            if 'c_user' in parsed_cookies and 'xs' in parsed_cookies:
                user_cookies_storage[user_id] = parsed_cookies
                await update.message.reply_text(
                    "✅ Cookies received successfully! Starting business creation loop..."
                )
                logger.info(f"User  {user_id} provided valid cookies. Initiating creation loop.")
                context.application.create_task(create_business_loop(update, context))
            else:
                await update.message.reply_text(
                    "❌ Invalid cookies. Please ensure they contain at least `c_user` and `xs`."
                )
                logger.warning(f"User  {user_id} provided invalid cookies format.")
        except Exception as e:
            await update.message.reply_text(f"❌ An error occurred while parsing cookies: {e}\nPlease ensure the format is correct.")
            logger.error(f"Error parsing cookies for user {user_id}: {e}")
    else:
        await update.message.reply_text("❌ No cookies provided. Please send them as a single line.")
        logger.warning(f"User  {user_id} sent empty message for cookies.")

async def create_business_loop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Continuously creates businesses until limit is reached or a persistent error occurs."""
    user_id = update.effective_user.id
    
    if user_id not in user_cookies_storage or not user_cookies_storage[user_id]:
        await update.message.reply_text(
            "❌ Your cookies are not saved. Please send them first as a text message."
        )
        return

    business_count = 0
    while True:
        business_count += 1
        await update.message.reply_text(f"🚀 Attempting to create Business #{business_count}...")
        logger.info(f"User  {user_id}: Starting creation for Business #{business_count}")

        max_retries_per_business = 3
        initial_delay = 5 # seconds
        
        current_biz_attempt_success = False
        for attempt in range(1, max_retries_per_business + 1):
            await update.message.reply_text(
                f"⏳ Business #{business_count}: Creation attempt {attempt}/{max_retries_per_business}..."
            )
            logger.info(f"User  {user_id}: Business #{business_count}, creation attempt {attempt}")

            success, biz_id, invitation_link, error_message = create_facebook_business(user_cookies_storage[user_id])

            if success == "LIMIT_REACHED":
                await update.message.reply_text(
                    "🛑 Facebook business creation limit reached for these cookies! Stopping further attempts."
                )
                logger.info(f"User  {user_id}: Business creation limit reached. Total created: {business_count - 1}")
                return # Exit the loop and function
            elif success:
                escaped_success_text = "🎉 Business created successfully\\!" 
                escaped_biz_id_label = "📊 \\*Business ID:\\*" 
                escaped_invitation_link_label = "🔗 \\*Invitation Link:\\*" 

                message = (
                    f"{escaped_success_text}\n"
                    f"{escaped_biz_id_label} `{escape_markdown(biz_id, version=2)}`\n"
                    f"{escaped_invitation_link_label} {escape_markdown(invitation_link, version=2)}"
                )
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                logger.info(f"User  {user_id}: Business #{business_count} created successfully on attempt {attempt}.")
                current_biz_attempt_success = True
                break # Break from inner retry loop, move to next business
            else:
                logger.error(f"User  {user_id}: Business #{business_count} creation failed on attempt {attempt}. Reason: {error_message}")
                
                if attempt < max_retries_per_business:
                    delay = initial_delay * (2 ** (attempt - 1)) # Exponential backoff
                    await update.message.reply_text(
                        f"❌ Business #{business_count}: Creation failed on attempt {attempt}. Reason: {escape_markdown(error_message, version=2)}\n"
                        f"Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
                else:
                    final_error_message = (
                        f"❌ Business #{business_count}: All {max_retries_per_business} attempts failed.\n"
                        f"Last error: {escape_markdown(error_message, version=2)}"
                    )
                    if biz_id:
                        final_error_message += f"\n📊 *Partial Business ID:* `{escape_markdown(biz_id, version=2)}`"
                    await update.message.reply_text(final_error_message, parse_mode='MarkdownV2')
                    logger.error(f"User  {user_id}: Business #{business_count}: All attempts failed. Final error: {error_message}")
        
        if not current_biz_attempt_success:
            await update.message.reply_text(
                f"⚠️ Business #{business_count} could not be created after multiple retries. Moving to next business attempt."
            )
            time.sleep(random.randint(10, 20))
        else:
            # If successful, wait a bit before trying the next one
            await update.message.reply_text(f"✅ Business #{business_count} created. Waiting a bit before next attempt...")
            time.sleep(random.randint(5, 15)) # Random delay between successful creations
