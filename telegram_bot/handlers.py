# facebook_business_bot/handlers.py
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from database.db_manager import DBManager
from facebook_creator import create_facebook_business

logger = logging.getLogger(__name__)
user_cookies_storage = {}  # Global variable to store user's cookies for the session

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and prompts for cookies."""
    await update.message.reply_text(
        "Welcome to the Facebook Business Creator Bot!\n"
        "To get started, please send your Facebook cookies as a single line of text or a .txt file.\n"
        "Example: `datr=...; sb=...; c_user=...; xs=...;`"
    )

async def handle_cookies_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, expecting them to be cookies.
    Starts the creation loop automatically if cookies are valid."""
    user_id = update.effective_user.id
    cookies_input_str = update.message.text.strip()

    if cookies_input_str:
        # إذا كانت المدخلات عبارة عن ملف، قم بقراءته
        if cookies_input_str.endswith('.txt'):
            try:
                with open(cookies_input_str, 'r') as file:
                    cookies_list = [line.strip() for line in file if line.strip()]  # تجاهل الأسطر الفارغة
                if not cookies_list:
                    await update.message.reply_text("❌ الملف فارغ أو لا يحتوي على كوكيز صحيحة.")
                    return
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ أثناء قراءة الملف: {e}")
                return
        else:
            # إذا كانت المدخلات نصية عادية
            cookies_list = [cookies_input_str]

        # تحقق من صحة الكوكيز
        valid_cookies = []
        for cookies in cookies_list:
            parsed_cookies = parse_cookies(cookies)
            if 'c_user' in parsed_cookies and 'xs' in parsed_cookies:
                valid_cookies.append(parsed_cookies)
            else:
                await update.message.reply_text("❌ الكوكيز غير صحيحة: " + cookies)
                return

        # تخزين الكوكيز في الذاكرة
        user_cookies_storage[user_id] = valid_cookies
        await update.message.reply_text("✅ تم استلام الكوكيز بنجاح! جاري بدء عملية إنشاء الأعمال...")
        logger.info(f"User  {user_id} provided valid cookies. Initiating creation loop.")
        # بدء حلقة الإنشاء
        context.application.create_task(create_business_loop(update, context))
    else:
        await update.message.reply_text("❌ لم يتم تقديم أي كوكيز. يرجى إرسالها كرسالة نصية.")
        logger.warning(f"User  {user_id} sent empty message for cookies.")

async def create_business_loop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Continuously creates businesses until limit is reached or a persistent error occurs."""
    user_id = update.effective_user.id
    
    if user_id not in user_cookies_storage or not user_cookies_storage[user_id]:
        await update.message.reply_text(
            "❌ الكوكيز الخاصة بك غير محفوظة. يرجى إرسالها أولاً كرسالة نصية."
        )
        return

    # استرجاع الكوكيز
    cookies_list = user_cookies_storage[user_id]
    business_count = 0

    while business_count < 50:  # تحديد الحد الأقصى لعدد الأعمال
        business_count += 1
        await update.message.reply_text(f"🚀 جاري محاولة إنشاء الحساب رقم {business_count}...")
        logger.info(f"User  {user_id}: Starting creation for Business #{business_count}")

        current_biz_attempt_success = False
        for attempt in range(1, MAX_RETRIES_PER_BUSINESS + 1):
            await update.message.reply_text(
                f"⏳ الحساب رقم {business_count}: محاولة الإنشاء {attempt}/{MAX_RETRIES_PER_BUSINESS}..."
            )
            logger.info(f"User  {user_id}: Business #{business_count}, creation attempt {attempt}")

            # استخدام الكوكيز من القائمة
            for cookies in cookies_list:
                success, biz_id, invitation_link, error_message = await create_facebook_business(
                    cookies, user_id, user.tempmail_api_key
                )

                if success:
                    message = (
                        f"🎉 تم إنشاء الحساب بنجاح!\n"
                        f"📊 معرف الحساب: {biz_id}\n"
                        f"🔗 رابط الدعوة: {invitation_link}"
                    )
                    await update.message.reply_text(message)
                    logger.info(f"User  {user_id}: Business #{business_count} created successfully on attempt {attempt}.")
                    current_biz_attempt_success = True
                    break  # Break from inner retry loop, move to next business
                else:
                    logger.error(f"User  {user_id}: Business #{business_count} creation failed on attempt {attempt}. Reason: {error_message}")

            if current_biz_attempt_success:
                break  # Exit the attempt loop if successful

        if not current_biz_attempt_success:
            await update.message.reply_text(
                f"⚠️ لم يتمكن من إنشاء الحساب رقم {business_count} بعد عدة محاولات. جاري الانتقال إلى محاولة إنشاء حساب آخر."
            )
            await asyncio.sleep(random.randint(10, 20))
