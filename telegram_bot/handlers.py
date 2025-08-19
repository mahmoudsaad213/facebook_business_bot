# facebook_business_bot/telegram_bot/handlers.py
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio
import random

from database.db_manager import db_manager
from services.facebook_creator import facebook_creator
from utils.helpers import parse_cookies
from config import MAX_RETRIES_PER_BUSINESS, INITIAL_RETRY_DELAY, MAX_BUSINESSES_PER_SESSION

logger = logging.getLogger(__name__)

# Global variable to store user's cookies for the session
user_cookies_storage = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and prompts for cookies."""
    user_id = update.effective_user.id
    user = db_manager.get_user(user_id)

    if not user:
        user = db_manager.add_user(user_id, is_admin=False)
        logger.info(f"New user {user_id} added to database.")

    username = update.effective_user.username or update.effective_user.first_name

    subscription_status = "غير مشترك"
    subscription_end_date_str = "لا يوجد"
    if user and db_manager.is_user_subscribed(user):
        subscription_status = "مشترك"
        subscription_end_date_str = user.subscription_end_date.strftime("%Y-%m-%d")

    welcome_message = (
        f"مرحبًا بك يا {username}!\n\n"
        f"أنت حاليًا: {subscription_status}\n"
        f"تاريخ انتهاء اشتراكك: {subscription_end_date_str}\n"
        f"الـ ID الخاص بك: {user_id}\n\n"
        "للبدء، يرجى إرسال الكوكيز الخاصة بك كسطر واحد من النص.\n"
        "أو يمكنك إرسال عدة كوكيز (كل واحدة في سطر منفصل).\n"
        "مثال: datr=...; sb=...; c_user=...; xs=...;"
    )

    keyboard = [
        [InlineKeyboardButton("تشغيل", callback_data="start_creation")],
        [InlineKeyboardButton("إيقاف", callback_data="stop_creation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def handle_cookies_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, expecting them to be cookies."""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    user = db_manager.get_user(user_id)
    if not user:
        user = db_manager.add_user(user_id, is_admin=False)
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

    if message_text:
        # معالجة الكوكيز المتعددة (كل سطر يحتوي على كوكيز منفصلة)
        lines = message_text.split('\n')
        cookies_list = []
        
        for line in lines:
            line = line.strip()
            if not line:  # تجاهل الأسطر الفارغة
                continue
                
            try:
                parsed_cookies = parse_cookies(line)
                if 'c_user' in parsed_cookies and 'xs' in parsed_cookies:
                    cookies_list.append(parsed_cookies)
                    logger.info(f"Valid cookies parsed for user {user_id}")
                else:
                    await update.message.reply_text(
                        f"❌ كوكيز غير صالحة (سطر {lines.index(line) + 1}). يرجى التأكد من أنها تحتوي على c_user و xs."
                    )
                    logger.warning(f"Invalid cookies format from user {user_id}")
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ في تحليل الكوكيز (سطر {lines.index(line) + 1}): {str(e)}")
                logger.error(f"Error parsing cookies for user {user_id}: {e}")
                
        if cookies_list:
            user_cookies_storage[user_id] = cookies_list
            await update.message.reply_text(
                f"✅ تم استلام {len(cookies_list)} كوكيز بنجاح! جاري بدء حلقة إنشاء الحسابات..."
            )
            logger.info(f"User {user_id} provided {len(cookies_list)} valid cookies. Initiating creation loop.")
            context.application.create_task(create_business_loop(update, context))
        else:
            await update.message.reply_text("❌ لم يتم العثور على أي كوكيز صالحة.")
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

    cookies_list = user_cookies_storage[user_id]
    business_count = user.businesses_created_count
    cookies_index = 0
    
    while business_count < MAX_BUSINESSES_PER_SESSION:
        user = db_manager.get_user(user_id)
        if not user or not db_manager.is_user_subscribed(user):
            await update.message.reply_text(
                "❌ اشتراكك غير نشط. توقف إنشاء الحسابات."
            )
            logger.warning(f"User {user_id} subscription became inactive during creation loop.")
            break

        business_count += 1
        current_cookies = cookies_list[cookies_index % len(cookies_list)]
        cookies_index += 1
        
        await update.message.reply_text(f"🚀 جاري محاولة إنشاء الحساب رقم {business_count}...")
        logger.info(f"User {user_id}: Starting creation for Business #{business_count}")

        current_biz_attempt_success = False
        for attempt in range(1, MAX_RETRIES_PER_BUSINESS + 1):
            await update.message.reply_text(
                f"⏳ الحساب رقم {business_count}: محاولة الإنشاء {attempt}/{MAX_RETRIES_PER_BUSINESS}..."
            )
            logger.info(f"User {user_id}: Business #{business_count}, creation attempt {attempt}")

            success, biz_id, invitation_link, error_message = await facebook_creator.create_facebook_business(
                current_cookies, user_id, user.tempmail_api_key
            )

            # التحقق من الأخطاء الحرجة
            if error_message and any(keyword in error_message.lower() for keyword in [
                "restricted", "account is currently restricted", "1357053", 
                "token not found", "cookies validity"
            ]):
                await update.message.reply_text(
                    f"❌ خطأ حرج: {error_message}\n"
                    "تم إيقاف عملية إنشاء الحسابات. يرجى مراجعة الكوكيز أو الحساب المستخدم."
                )
                logger.error(f"User {user_id}: Critical error encountered. Stopping creation loop. Error: {error_message}")
                return

            if success == "LIMIT_REACHED":
                await update.message.reply_text(
                    "🛑 تم الوصول إلى حد إنشاء حسابات فيسبوك للأعمال لهذه الكوكيز!"
                )
                logger.info(f"User {user_id}: Business creation limit reached. Total created: {business_count - 1}")
                
                # جرب الكوكيز التالية إذا كانت متاحة
                if len(cookies_list) > 1:
                    await update.message.reply_text("جاري تجربة الكوكيز التالية...")
                    break
                else:
                    return
            elif success:
                message = (
                    f"🎉 تم إنشاء الحساب بنجاح!\n"
                    f"📊 معرف الحساب: {biz_id}\n"
                    f"🔗 رابط الدعوة: {invitation_link}"
                )
                await update.message.reply_text(message)
                logger.info(f"User {user_id}: Business #{business_count} created successfully on attempt {attempt}.")
                
                user.businesses_created_count = business_count
                db_manager.update_user(user)
                
                current_biz_attempt_success = True
                break
            else:
                logger.error(f"User {user_id}: Business #{business_count} creation failed on attempt {attempt}. Reason: {error_message}")
                
                if attempt < MAX_RETRIES_PER_BUSINESS:
                    delay = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
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
                    await update.message.reply_text(final_error_message)
                    logger.error(f"User {user_id}: Business #{business_count}: All attempts failed. Final error: {error_message}")
        
        if not current_biz_attempt_success:
            await update.message.reply_text(
                f"⚠️ لم يتمكن من إنشاء الحساب رقم {business_count} بعد عدة محاولات."
            )
            await asyncio.sleep(random.randint(10, 20))
        else:
            await update.message.reply_text(f"✅ تم إنشاء الحساب رقم {business_count}. جاري الانتظار قليلاً قبل المحاولة التالية...")
            await asyncio.sleep(random.randint(5, 15))
    
    await update.message.reply_text(f"✅ انتهت عملية إنشاء الحسابات. تم إنشاء {business_count} حساب.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message."""
    await update.message.reply_text(
        "أنا بوت لإنشاء حسابات فيسبوك للأعمال.\n\n"
        "الخطوات:\n"
        "1. أرسل لي الكوكيز الخاصة بك كسطر واحد من النص.\n"
        "2. سأبدأ تلقائيًا بإنشاء الحسابات لك حتى يتم الوصول إلى الحد الأقصى.\n\n"
        "ملاحظة: قد تستغرق العملية بضع دقائق لكل حساب."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's subscription status and usage information."""
    user_id = update.effective_user.id
    user = db_manager.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ لم يتم العثور على المستخدم في قاعدة البيانات.")
        return

    subscription_status = "غير مشترك"
    subscription_end_date_str = "لا يوجد"
    if db_manager.is_user_subscribed(user):
        subscription_status = "مشترك"
        subscription_end_date_str = user.subscription_end_date.strftime("%Y-%m-%d")

    await update.message.reply_text(
        f"📊 حالة الاشتراك:\n"
        f"الـ ID الخاص بك: {user_id}\n"
        f"حالة الاشتراك: {subscription_status}\n"
        f"تاريخ انتهاء الاشتراك: {subscription_end_date_str}\n"
        f"عدد الحسابات التي تم إنشاؤها: {user.businesses_created_count}"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    escaped_error_message = str(context.error)
    
    message = (
        "حدث خطأ غير متوقع أثناء معالجة طلبك\\. "
        "تم إبلاغ المطورين\\.\n\n"
        f"الخطأ: `{escaped_error_message}`"
    )
    
    if update.effective_message:
        await update.effective_message.reply_text(message, parse_mode='MarkdownV2')
    else:
        logger.warning("Error handler called without an effective message.")
