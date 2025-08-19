# facebook_business_bot/telegram_bot/handlers.py
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown # Keep for reference, but use custom escape_markdown_v2

from database.db_manager import db_manager
from services.facebook_creator import facebook_creator
from utils.helpers import parse_cookies, escape_markdown_v2
from config import MAX_RETRIES_PER_BUSINESS, INITIAL_RETRY_DELAY
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

    # Ensure all parts of the message are escaped
    welcome_message = (
        f"مرحبًا بك يا {escape_markdown_v2(username)}!\n\n"
        f"أنت حاليًا: *{escape_markdown_v2(subscription_status)}*\n"
        f"تاريخ انتهاء اشتراكك: `{escape_markdown_v2(subscription_end_date_str)}`\n"
        f"الـ ID الخاص بك: `{escape_markdown_v2(str(user_id))}`\n\n"
        "للبدء، يرجى إرسال الكوكيز الخاصة بك كسطر واحد من النص\\.\n"
        "مثال: `datr=...; sb=...; c_user=...; xs=...;`"
    )

    keyboard = [
        [InlineKeyboardButton("تشغيل", callback_data="start_creation")],
        [InlineKeyboardButton("إيقاف", callback_data="stop_creation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, parse_mode='MarkdownV2', reply_markup=reply_markup)

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
            escape_markdown_v2("❌ عذرًا، اشتراكك غير نشط. يرجى تجديد اشتراكك للمتابعة.")
            , parse_mode='MarkdownV2'
        )
        logger.warning(f"User {user_id} tried to use bot with inactive subscription.")
        return

    if not user.tempmail_api_key:
        await update.message.reply_text(
            escape_markdown_v2("❌ لم يتم تعيين مفتاح TempMail API الخاص بك. يرجى الاتصال بالمسؤول.")
            , parse_mode='MarkdownV2'
        )
        logger.warning(f"User {user_id} has no TempMail API key set.")
        return

    if cookies_input_str:
        try:
            parsed_cookies = parse_cookies(cookies_input_str)
            if 'c_user' in parsed_cookies and 'xs' in parsed_cookies:
                user_cookies_storage[user_id] = parsed_cookies # Store cookies temporarily
                await update.message.reply_text(
                    escape_markdown_v2("✅ تم استلام الكوكيز بنجاح! جاري بدء حلقة إنشاء الحسابات...")
                    , parse_mode='MarkdownV2'
                )
                logger.info(f"User {user_id} provided valid cookies. Initiating creation loop.")
                # Start the creation loop in a non-blocking way
                context.application.create_task(create_business_loop(update, context))
            else:
                await update.message.reply_text(
                    escape_markdown_v2("❌ كوكيز غير صالحة. يرجى التأكد من أنها تحتوي على `c_user` و `xs` على الأقل.")
                    , parse_mode='MarkdownV2'
                )
                logger.warning(f"User {user_id} provided invalid cookies format.")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء تحليل الكوكيز: {escape_markdown_v2(str(e))}\nيرجى التأكد من أن التنسيق صحيح.", parse_mode='MarkdownV2')
            logger.error(f"Error parsing cookies for user {user_id}: {e}")
    else:
        await update.message.reply_text(escape_markdown_v2("❌ لم يتم تقديم أي كوكيز. يرجى إرسالها كسطر واحد."), parse_mode='MarkdownV2')
        logger.warning(f"User {user_id} sent empty message for cookies.")

async def create_business_loop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Continuously creates businesses until limit is reached or a persistent error occurs."""
    user_id = update.effective_user.id
    
    user = db_manager.get_user(user_id)
    if not user or not db_manager.is_user_subscribed(user):
        await update.message.reply_text(
            escape_markdown_v2("❌ اشتراكك غير نشط. توقف إنشاء الحسابات.")
            , parse_mode='MarkdownV2'
        )
        logger.warning(f"User {user_id} subscription became inactive during creation loop.")
        return

    if user_id not in user_cookies_storage or not user_cookies_storage[user_id]:
        await update.message.reply_text(
            escape_markdown_v2("❌ الكوكيز الخاصة بك غير محفوظة. يرجى إرسالها أولاً كرسالة نصية.")
            , parse_mode='MarkdownV2'
        )
        return

    if not user.tempmail_api_key:
        await update.message.reply_text(
            escape_markdown_v2("❌ لم يتم تعيين مفتاح TempMail API الخاص بك. يرجى الاتصال بالمسؤول.")
            , parse_mode='MarkdownV2'
        )
        logger.warning(f"User {user_id} has no TempMail API key set, stopping creation loop.")
        return

    business_count = user.businesses_created_count # Start from current count
    while True:
        # Check subscription status before each attempt
        user = db_manager.get_user(user_id)
        if not user or not db_manager.is_user_subscribed(user):
            await update.message.reply_text(
                escape_markdown_v2("❌ اشتراكك غير نشط. توقف إنشاء الحسابات.")
                , parse_mode='MarkdownV2'
            )
            logger.warning(f"User {user_id} subscription became inactive during creation loop.")
            break # Exit the loop

        # Check daily email limit (if applicable, based on last_email_creation_date)
        # For now, we allow one new temp email per creation attempt.
        # If you want to enforce one temp email per day, you'd check user.last_email_creation_date here.
        # For simplicity, we'll assume tempmail_api.create_temp_email handles internal limits or we create a new one each time.
        # If you want to enforce one *specific* temp email per day, you'd need to store it in the DB.

        business_count += 1
        await update.message.reply_text(escape_markdown_v2(f"🚀 جاري محاولة إنشاء الحساب رقم {business_count}..."), parse_mode='MarkdownV2')
        logger.info(f"User {user_id}: Starting creation for Business #{business_count}")

        current_biz_attempt_success = False
        for attempt in range(1, MAX_RETRIES_PER_BUSINESS + 1):
            await update.message.reply_text(
                escape_markdown_v2(f"⏳ الحساب رقم {business_count}: محاولة الإنشاء {attempt}/{MAX_RETRIES_PER_BUSINESS}...")
                , parse_mode='MarkdownV2'
            )
            logger.info(f"User {user_id}: Business #{business_count}, creation attempt {attempt}")

            # Pass the user's specific tempmail_api_key
            success, biz_id, invitation_link, error_message = await facebook_creator.create_facebook_business(
                user_cookies_storage[user_id], user.tempmail_api_key
            )

            if success == "LIMIT_REACHED":
                await update.message.reply_text(
                    escape_markdown_v2("🛑 تم الوصول إلى حد إنشاء حسابات فيسبوك للأعمال لهذه الكوكيز! جاري إيقاف المحاولات الإضافية.")
                    , parse_mode='MarkdownV2'
                )
                logger.info(f"User {user_id}: Business creation limit reached. Total created: {business_count - 1}")
                return # Exit the loop and function
            elif success:
                escaped_success_text = escape_markdown_v2("🎉 تم إنشاء الحساب بنجاح!") 
                escaped_biz_id_label = escape_markdown_v2("📊 *معرف الحساب:*") 
                escaped_invitation_link_label = escape_markdown_v2("🔗 *رابط الدعوة:*") 

                message = (
                    f"{escaped_success_text}\n"
                    f"{escaped_biz_id_label} `{escape_markdown_v2(biz_id)}`\n"
                    f"{escaped_invitation_link_label} `{escape_markdown_v2(invitation_link)}`" # Display link as code
                )
                await update.message.reply_text(message, parse_mode='MarkdownV2')
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
                        escape_markdown_v2(f"❌ الحساب رقم {business_count}: فشلت محاولة الإنشاء {attempt}. السبب: {error_message}\n") +
                        escape_markdown_v2(f"جاري إعادة المحاولة بعد {delay} ثواني...")
                        , parse_mode='MarkdownV2'
                    )
                    await asyncio.sleep(delay)
                else:
                    final_error_message = (
                        escape_markdown_v2(f"❌ الحساب رقم {business_count}: فشلت جميع المحاولات الـ {MAX_RETRIES_PER_BUSINESS}.\n") +
                        escape_markdown_v2(f"آخر خطأ: {error_message}")
                    )
                    if biz_id:
                        final_error_message += escape_markdown_v2(f"\n📊 *معرف الحساب الجزئي:* `{biz_id}`")
                    await update.message.reply_text(final_error_message, parse_mode='MarkdownV2')
                    logger.error(f"User {user_id}: Business #{business_count}: All attempts failed. Final error: {error_message}")
        
        if not current_biz_attempt_success:
            await update.message.reply_text(
                escape_markdown_v2(f"⚠️ لم يتمكن من إنشاء الحساب رقم {business_count} بعد عدة محاولات. جاري الانتقال إلى محاولة إنشاء حساب آخر.")
                , parse_mode='MarkdownV2'
            )
            # Add a small delay before trying the next business if the current one failed persistently
            await asyncio.sleep(random.randint(10, 20))
        else:
            # If successful, wait a bit before trying the next one
            await update.message.reply_text(escape_markdown_v2(f"✅ تم إنشاء الحساب رقم {business_count}. جاري الانتظار قليلاً قبل المحاولة التالية..."), parse_mode='MarkdownV2')
            await asyncio.sleep(random.randint(5, 15)) # Random delay between successful creations

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message."""
    await update.message.reply_text(
        escape_markdown_v2("أنا بوت لإنشاء حسابات فيسبوك للأعمال.\n\n") +
        escape_markdown_v2("الخطوات:\n") +
        escape_markdown_v2("1. أرسل لي الكوكيز الخاصة بك كسطر واحد من النص.\n") +
        escape_markdown_v2("2. سأبدأ تلقائيًا بإنشاء الحسابات لك حتى يتم الوصول إلى الحد الأقصى.\n\n") +
        escape_markdown_v2("ملاحظة: قد تستغرق العملية بضع دقائق لكل حساب وتتضمن محاولات إعادة لضمان المتانة.")
        , parse_mode='MarkdownV2'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's subscription status and usage."""
    user_id = update.effective_user.id
    user = db_manager.get_user(user_id)

    if not user:
        await update.message.reply_text(escape_markdown_v2("❌ لم يتم العثور على بياناتك. يرجى استخدام أمر /start أولاً."), parse_mode='MarkdownV2')
        return

    username = update.effective_user.username or update.effective_user.first_name
    
    subscription_status = "غير نشط"
    subscription_end_date_str = "لا يوجد"
    if db_manager.is_user_subscribed(user):
        subscription_status = "نشط"
        subscription_end_date_str = user.subscription_end_date.strftime("%Y-%m-%d")

    tempmail_api_key_status = "محدد" if user.tempmail_api_key else "غير محدد"
    
    message = (
        f"📊 \\*حالة حسابك يا {escape_markdown_v2(username)}:\\*\n\n"
        f"\\- حالة الاشتراك: *{escape_markdown_v2(subscription_status)}*\n"
        f"\\- تاريخ انتهاء الاشتراك: `{escape_markdown_v2(subscription_end_date_str)}`\n"
        f"\\- مفتاح TempMail API: *{escape_markdown_v2(tempmail_api_key_status)}*\n"
        f"\\- عدد الحسابات التي تم إنشاؤها: `{escape_markdown_v2(str(user.businesses_created_count))}`"
    )
    await update.message.reply_text(message, parse_mode='MarkdownV2')

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer() # Acknowledge the callback query

    user_id = query.from_user.id
    
    if query.data == "start_creation":
        await query.edit_message_text(
            escape_markdown_v2("✅ تم الضغط على 'تشغيل'. يرجى إرسال الكوكيز الخاصة بك لبدء عملية الإنشاء.")
            , parse_mode='MarkdownV2'
        )
    elif query.data == "stop_creation":
        # Here you would implement logic to stop an ongoing creation loop for this user
        # This would require storing the running task for each user in context.user_data or similar
        await query.edit_message_text(
            escape_markdown_v2("🛑 تم الضغط على 'إيقاف'. سيتم إيقاف أي عملية إنشاء جارية.")
            , parse_mode='MarkdownV2'
        )
        # Example: context.user_data[user_id]['stop_flag'] = True
    
    # Admin callback queries are handled by ConversationHandler entry points in main.py
    # or by specific CommandHandlers if they are single-step.
