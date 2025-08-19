# facebook_business_bot/telegram_bot/handlers.py
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_RETRIES_PER_BUSINESS, INITIAL_RETRY_DELAY # Add this line

# Removed telegram.helpers.escape_markdown as we are not using MarkdownV2

from database.db_manager import db_manager
from services.facebook_creator import facebook_creator
from utils.helpers import parse_cookies # Removed escape_markdown_v2 as we are not using MarkdownV2
import asyncio # For async operations
import random # For random delays

logger = logging.getLogger(__name__)

# Global variable to store user's cookies for the session (temporary, will be replaced by DB for persistent data)
user_cookies_storage = {} # Stores cookies per user_id

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and prompts for cookies."""
    user_id = update.effective_user.id
    user = db_manager.get_user(user_id)

    if not user:
        # First time user, add them to DB as non-admin
        user = db_manager.add_user(user_id, is_admin=False)
        logger.info(f"New user {user_id} added to database.")

    username = update.effective_user.username or update.effective_user.first_name

    subscription_status = "غير مشترك"
    subscription_end_date_str = "لا يوجد"
    if user and db_manager.is_user_subscribed(user):
        subscription_status = "مشترك"
        subscription_end_date_str = user.subscription_end_date.strftime("%Y-%m-%d")

    # Removed all MarkdownV2 formatting and escape_markdown_v2 calls
    welcome_message = (
        f"مرحبًا بك يا {username}!\n\n"
        f"أنت حاليًا: {subscription_status}\n"
        f"تاريخ انتهاء اشتراكك: {subscription_end_date_str}\n"
        f"الـ ID الخاص بك: {user_id}\n\n"
        "للبدء، يرجى إرسال الكوكيز الخاصة بك كسطر واحد من النص.\n"
        "مثال: datr=...; sb=...; c_user=...; xs=...;"
    )

    keyboard = [
        [InlineKeyboardButton("تشغيل", callback_data="start_creation")],
        [InlineKeyboardButton("إيقاف", callback_data="stop_creation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup) # Removed parse_mode

async def handle_cookies_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, expecting them to be cookies.
    Starts the creation loop automatically if cookies are valid."""
    user_id = update.effective_user.id
    cookies_input_str = update.message.text.strip()

    user = db_manager.get_user(user_id)
    if not user:
        user = db_manager.add_user(user_id, is_admin=False) # Add user if not exists
        logger.info(f"User {user_id} added to DB via message handler.")

    if not db_manager.is_user_subscribed(user):
        await update.message.reply_text(
            "❌ عذرًا، اشتراكك غير نشط. يرجى تجديد اشتراكك للمتابعة."
        )
        logger.warning(f"User {user_id} tried to use bot with inactive subscription.")
        return

    if not user.tempmail_api_key:
        await update.message.reply_text(
            "❌ لم يتم تعيين مفتاح TempMail API الخاص بك. يرجى الاتصال بالمسؤول."
        )
        logger.warning(f"User {user_id} has no TempMail API key set.")
        return

    if cookies_input_str:
        try:
            parsed_cookies = parse_cookies(cookies_input_str)
            if 'c_user' in parsed_cookies and 'xs' in parsed_cookies:
                user_cookies_storage[user_id] = parsed_cookies # Store cookies temporarily
                await update.message.reply_text(
                    "✅ تم استلام الكوكيز بنجاح! جاري بدء حلقة إنشاء الحسابات..."
                )
                logger.info(f"User {user_id} provided valid cookies. Initiating creation loop.")
                # Start the creation loop in a non-blocking way
                context.application.create_task(create_business_loop(update, context))
            else:
                await update.message.reply_text(
                    "❌ كوكيز غير صالحة. يرجى التأكد من أنها تحتوي على c_user و xs على الأقل."
                )
                logger.warning(f"User {user_id} provided invalid cookies format.")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء تحليل الكوكيز: {e}\nيرجى التأكد من أن التنسيق صحيح.")
            logger.error(f"Error parsing cookies for user {user_id}: {e}")
    else:
        await update.message.reply_text("❌ لم يتم تقديم أي كوكيز. يرجى إرسالها كسطر واحد.")
        logger.warning(f"User {user_id} sent empty message for cookies.")

async def create_business_loop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Continuously creates businesses until limit is reached or a persistent error occurs."""
    user_id = update.effective_user.id
    
    if user_id not in user_cookies_storage or not user_cookies_storage[user_id]:
        await update.message.reply_text(
            "❌ Your cookies are not saved. Please send them first as a text message."
        )
        return

    # استرجاع المستخدم من قاعدة البيانات
    user = db_manager.get_user(user_id)
    if not user or not user.tempmail_api_key:
        await update.message.reply_text("❌ TempMail API Key is not set for your account.")
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

            success, biz_id, invitation_link, error_message = await facebook_creator.create_facebook_business(
                user_cookies_storage[user_id],
                user_id,  # أو telegram_user_id
                user.tempmail_api_key  # تمرير مفتاح API الخاص بـ TempMail
            )

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
                    await asyncio.sleep(delay)  # Use asyncio.sleep for non-blocking delay
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
            # Add a small delay before trying the next business if the current one failed persistently
            await asyncio.sleep(random.randint(10, 20))
        else:
            # If successful, wait a bit before trying the next one
            await update.message.reply_text(f"✅ Business #{business_count} created. Waiting a bit before next attempt...")
            await asyncio.sleep(random.randint(5, 15)) # Random delay between successful creations

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message."""
    await update.message.reply_text(
        "أنا بوت لإنشاء حسابات فيسبوك للأعمال.\n\n"
        "الخطوات:\n"
        "1. أرسل لي الكوكيز الخاصة بك كسطر واحد من النص.\n"
        "2. سأبدأ تلقائيًا بإنشاء الحسابات لك حتى يتم الوصول إلى الحد الأقصى.\n\n"
        "ملاحظة: قد تستغرق العملية بضع دقائق لكل حساب وتتضمن محاولات إعادة لضمان المتانة."
    ) # Removed parse_mode

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's subscription status and usage."""
    user_id = update.effective_user.id
    user = db_manager.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ لم يتم العثور على بياناتك. يرجى استخدام أمر /start أولاً.")
        return

    username = update.effective_user.username or update.effective_user.first_name
    
    subscription_status = "غير نشط"
    subscription_end_date_str = "لا يوجد"
    if db_manager.is_user_subscribed(user):
        subscription_status = "نشط"
        subscription_end_date_str = user.subscription_end_date.strftime("%Y-%m-%d")

    tempmail_api_key_status = "محدد" if user.tempmail_api_key else "غير محدد"
    
    message = (
        f"📊 حالة حسابك يا {username}:\n\n"
        f"- حالة الاشتراك: {subscription_status}\n"
        f"- تاريخ انتهاء الاشتراك: {subscription_end_date_str}\n"
        f"- مفتاح TempMail API: {tempmail_api_key_status}\n"
        f"- عدد الحسابات التي تم إنشاؤها: {user.businesses_created_count}"
    )
    await update.message.reply_text(message) # Removed parse_mode

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer() # Acknowledge the callback query

    user_id = query.from_user.id
    
    if query.data == "start_creation":
        await query.edit_message_text(
            "✅ تم الضغط على 'تشغيل'. يرجى إرسال الكوكيز الخاصة بك لبدء عملية الإنشاء."
        ) # Removed parse_mode
    elif query.data == "stop_creation":
        await query.edit_message_text(
            "🛑 تم الضغط على 'إيقاف'. سيتم إيقاف أي عملية إنشاء جارية."
        ) # Removed parse_mode
    
