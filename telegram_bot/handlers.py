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
    
    user = db_manager.get_user(user_id)
    if not user or not db_manager.is_user_subscribed(user):
        await update.message.reply_text(
            "❌ اشتراكك غير نشط. توقف إنشاء الحسابات."
        )
        logger.warning(f"User {user_id} subscription became inactive during creation loop.")
        return

    if user_id not in user_cookies_storage or not user_cookies_storage[user_id]:
        await update.message.reply_text(
            "❌ الكوكيز الخاصة بك غير محفوظة. يرجى إرسالها أولاً كرسالة نصية."
        )
        return

    if not user.tempmail_api_key:
        await update.message.reply_text(
            "❌ لم يتم تعيين مفتاح TempMail API الخاص بك. يرجى الاتصال بالمسؤول."
        )
        logger.warning(f"User {user_id} has no TempMail API key set, stopping creation loop.")
        return

    business_count = user.businesses_created_count # Start from current count
    while True:
        # Check subscription status before each attempt
        user = db_manager.get_user(user_id)
        if not user or not db_manager.is_user_subscribed(user):
            await update.message.reply_text(
                "❌ اشتراكك غير نشط. توقف إنشاء الحسابات."
            )
            logger.warning(f"User {user_id} subscription became inactive during creation loop.")
            break # Exit the loop

        business_count += 1
        await update.message.reply_text(f"🚀 جاري محاولة إنشاء الحساب رقم {business_count}...")
        logger.info(f"User {user_id}: Starting creation for Business #{business_count}")

        current_biz_attempt_success = False
        for attempt in range(1, MAX_RETRIES_PER_BUSINESS + 1):
            await update.message.reply_text(
                f"⏳ الحساب رقم {business_count}: محاولة الإنشاء {attempt}/{MAX_RETRIES_PER_BUSINESS}..."
            )
            logger.info(f"User {user_id}: Business #{business_count}, creation attempt {attempt}")

            # Pass the user's specific tempmail_api_key
            success, biz_id, invitation_link, error_message = await facebook_creator.create_facebook_business(
                user_cookies_storage[user_id], user.tempmail_api_key
            )

            if success == "LIMIT_REACHED":
                await update.message.reply_text(
                    "🛑 تم الوصول إلى حد إنشاء حسابات فيسبوك للأعمال لهذه الكوكيز! جاري إيقاف المحاولات الإضافية."
                )
                logger.info(f"User {user_id}: Business creation limit reached. Total created: {business_count - 1}")
                return # Exit the loop and function
            elif success:
                # Removed MarkdownV2 formatting
                message = (
                    f"🎉 تم إنشاء الحساب بنجاح!\n"
                    f"📊 معرف الحساب: {biz_id}\n"
                    f"🔗 رابط الدعوة: {invitation_link}"
                )
                await update.message.reply_text(message) # Removed parse_mode
                logger.info(f"User {user_id}: Business #{business_count} created successfully on attempt {attempt}.")
                
                # Update user's created count in DB
                user.businesses_created_count = business_count
                db_manager.update_user(user)
                
                current_biz_attempt_success = True
                break # Break from inner retry loop, move to next business
            else:
                logger.error(f"User {user_id}: Business #{business_count} creation failed on attempt {attempt}. Reason: {error_message}")
                
                if attempt < MAX_RETRIES_PER_BUSINESS:
                    delay = INITIAL_RETRY_DELAY * (2 ** (attempt - 1)) # Exponential backoff
                    await update.message.reply_text(
                        f"❌ الحساب رقم {business_count}: فشلت محاولة الإنشاء {attempt}. السبب: {error_message}\n"
                        f"جاري إعادة المحاولة بعد {delay} ثواني..."
                    )
                    await asyncio.sleep(delay)
                else:
                    final_error_message = (
                        f"❌ الحساب رقم {business_count}: فشلت جميع المحاولات الـ {MAX_RETRIES_PER_BUSINESS}.\n"
                        f"آخر خطأ: {error_message}"
                    )
                    if biz_id:
                        final_error_message += f"\n📊 معرف الحساب الجزئي: {biz_id}"
                    await update.message.reply_text(final_error_message) # Removed parse_mode
                    logger.error(f"User {user_id}: Business #{business_count}: All attempts failed. Final error: {error_message}")
        
        if not current_biz_attempt_success:
            await update.message.reply_text(
                f"⚠️ لم يتمكن من إنشاء الحساب رقم {business_count} بعد عدة محاولات. جاري الانتقال إلى محاولة إنشاء حساب آخر."
            )
            # Add a small delay before trying the next business if the current one failed persistently
            await asyncio.sleep(random.randint(10, 20))
        else:
            # If successful, wait a bit before trying the next one
            await update.message.reply_text(f"✅ تم إنشاء الحساب رقم {business_count}. جاري الانتظار قليلاً قبل المحاولة التالية...")
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
    
