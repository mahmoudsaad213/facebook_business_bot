# facebook_business_bot/telegram_bot/admin_handlers.py
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
# Removed telegram.helpers.escape_markdown as we are not using MarkdownV2

from config import ADMIN_ID
from database.db_manager import db_manager
# Removed escape_markdown_v2 as we are not using MarkdownV2

logger = logging.getLogger(__name__)

# --- Conversation States for Admin Commands ---
# These states will be used by ConversationHandler to manage multi-step admin commands
ADD_USER_STATE_ID, ADD_USER_STATE_API_KEY, ADD_USER_STATE_SUB_DAYS = range(3)
DELETE_USER_STATE_ID = range(3, 4) # Use range for unique states
SEND_MESSAGE_STATE = range(4, 5)
REWARD_USERS_STATE_DAYS = range(5, 6)
RENEW_USER_STATE_ID, RENEW_USER_STATE_DAYS = range(6, 8)

# --- Admin Check Decorator ---
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("❌ عذرًا، هذا الأمر مخصص للمسؤولين فقط.")
            elif update.callback_query:
                await update.callback_query.answer("❌ عذرًا، هذا الأمر مخصص للمسؤولين فقط.", show_alert=True)
            logger.warning(f"Non-admin user {user_id} tried to access admin command: {func.__name__}")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# --- Admin Commands ---

@admin_only
async def admin_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the admin menu."""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مشترك", callback_data="admin_add_user_start")],
        [InlineKeyboardButton("➖ حذف مشترك", callback_data="admin_delete_user_start")],
        [InlineKeyboardButton("📋 قائمة المشتركين", callback_data="admin_list_users")],
        [InlineKeyboardButton("✉️ إرسال رسالة للكل", callback_data="admin_send_message_to_all_start")],
        [InlineKeyboardButton("🎁 مكافأة المشتركين", callback_data="admin_reward_users_start")],
        [InlineKeyboardButton("🔄 تجديد اشتراك مستخدم", callback_data="admin_renew_user_subscription_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("لوحة تحكم المسؤول:", reply_markup=reply_markup) # Removed parse_mode
    elif update.callback_query:
        await update.callback_query.edit_message_text("لوحة تحكم المسؤول:", reply_markup=reply_markup) # Removed parse_mode

# --- Admin Callback Query Handlers (for starting multi-step commands) ---

@admin_only
async def admin_add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the add user conversation."""
    await update.callback_query.edit_message_text(
        "الرجاء إرسال معرف تيليجرام (Telegram ID) للمشترك الجديد:"
    ) # Removed parse_mode
    return ADD_USER_STATE_ID

@admin_only
async def admin_delete_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the delete user conversation."""
    await update.callback_query.edit_message_text(
        "الرجاء إرسال معرف تيليجرام (Telegram ID) للمشترك الذي تريد حذفه:"
    ) # Removed parse_mode
    return DELETE_USER_STATE_ID

@admin_only
async def admin_send_message_to_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the send message to all conversation."""
    await update.callback_query.edit_message_text(
        "الرجاء إرسال الرسالة التي تريد إرسالها لجميع المشتركين:"
    ) # Removed parse_mode
    return SEND_MESSAGE_STATE

@admin_only
async def admin_reward_users_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the reward users conversation."""
    await update.callback_query.edit_message_text(
        "الرجاء إرسال عدد الأيام التي تريد مكافأة جميع المشتركين بها:"
    ) # Removed parse_mode
    return REWARD_USERS_STATE_DAYS

@admin_only
async def admin_renew_user_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the renew user subscription conversation."""
    await update.callback_query.edit_message_text(
        "الرجاء إرسال معرف تيليجرام (Telegram ID) للمشترك الذي تريد تجديد اشتراكه:"
    ) # Removed parse_mode
    return RENEW_USER_STATE_ID

# --- Admin Conversation Step Handlers ---

@admin_only
async def add_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the Telegram ID for adding a user."""
    try:
        telegram_id = int(update.message.text)
        context.user_data['add_user_telegram_id'] = telegram_id
        await update.message.reply_text("الرجاء إرسال مفتاح TempMail API للمشترك:") # Removed parse_mode
        return ADD_USER_STATE_API_KEY
    except ValueError:
        await update.message.reply_text("❌ معرف تيليجرام غير صالح. يرجى إرسال رقم صحيح.") # Removed parse_mode
        return ADD_USER_STATE_ID # Stay in the same state to retry

@admin_only
async def add_user_get_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the API Key for adding a user."""
    api_key = update.message.text.strip()
    context.user_data['add_user_api_key'] = api_key
    await update.message.reply_text("الرجاء إرسال عدد أيام الاشتراك:") # Removed parse_mode
    return ADD_USER_STATE_SUB_DAYS

@admin_only
async def add_user_get_sub_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the subscription days and finalizes adding a user."""
    try:
        subscription_days = int(update.message.text)
        telegram_id = context.user_data['add_user_telegram_id']
        api_key = context.user_data['add_user_api_key']

        user = db_manager.get_user(telegram_id)
        if user:
            await update.message.reply_text(f"⚠️ المستخدم {telegram_id} موجود بالفعل. جاري تحديث بياناته.") # Removed parse_mode
            user.tempmail_api_key = api_key
            user.subscription_end_date = date.today() + timedelta(days=subscription_days)
            db_manager.update_user(user)
            await update.message.reply_text(f"✅ تم تحديث بيانات المستخدم {telegram_id} بنجاح. تاريخ انتهاء الاشتراك: {user.subscription_end_date}") # Removed parse_mode
        else:
            new_user = db_manager.add_user(telegram_id, is_admin=False, tempmail_api_key=api_key, subscription_days=subscription_days)
            if new_user:
                await update.message.reply_text(f"✅ تم إضافة المستخدم {telegram_id} بنجاح. تاريخ انتهاء الاشتراك: {new_user.subscription_end_date}") # Removed parse_mode
            else:
                await update.message.reply_text(f"❌ فشل إضافة المستخدم {telegram_id}.") # Removed parse_mode
        
        # Clear user_data and end conversation
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ عدد الأيام غير صالح. يرجى إرسال رقم صحيح.") # Removed parse_mode
        return ADD_USER_STATE_SUB_DAYS # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء إضافة المستخدم: {e}") # Removed parse_mode
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def delete_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the Telegram ID for deleting a user."""
    try:
        telegram_id = int(update.message.text)
        user_to_delete = db_manager.get_user(telegram_id)
        if not user_to_delete:
            await update.message.reply_text(f"⚠️ المستخدم {telegram_id} غير موجود.") # Removed parse_mode
            context.user_data.clear()
            return ConversationHandler.END
        
        if db_manager.delete_user(telegram_id):
            await update.message.reply_text(f"✅ تم حذف المستخدم {telegram_id} بنجاح.") # Removed parse_mode
        else:
            await update.message.reply_text(f"❌ فشل حذف المستخدم {telegram_id}.") # Removed parse_mode
        
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ معرف تيليجرام غير صالح. يرجى إرسال رقم صحيح.") # Removed parse_mode
        return DELETE_USER_STATE_ID # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء حذف المستخدم: {e}") # Removed parse_mode
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def send_message_to_all_get_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the message to send to all users."""
    message_text = update.message.text
    users = db_manager.get_all_users()
    sent_count = 0
    failed_count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user.telegram_id, text=message_text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to user {user.telegram_id}: {e}")
            failed_count += 1
    
    await update.message.reply_text(f"✅ تم إرسال الرسالة إلى {sent_count} مستخدم. فشل إرسالها إلى {failed_count} مستخدم.") # Removed parse_mode
    context.user_data.clear()
    return ConversationHandler.END

@admin_only
async def reward_users_get_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the number of days to reward all users."""
    try:
        days = int(update.message.text)
        if days <= 0:
            await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقمًا موجبًا.") # Removed parse_mode
            return REWARD_USERS_STATE_DAYS # Stay in the same state to retry
        
        updated_count = db_manager.reward_all_users(days)
        await update.message.reply_text(f"✅ تم مكافأة {updated_count} مستخدمًا بـ {days} أيام إضافية.") # Removed parse_mode
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ عدد الأيام غير صالح. يرجى إرسال رقم صحيح.") # Removed parse_mode
        return REWARD_USERS_STATE_DAYS # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error rewarding users: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء مكافأة المستخدمين: {e}") # Removed parse_mode
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def renew_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the Telegram ID for renewing a user's subscription."""
    try:
        telegram_id = int(update.message.text)
        context.user_data['renew_user_telegram_id'] = telegram_id
        await update.message.reply_text("الرجاء إرسال عدد الأيام التي تريد تجديد الاشتراك بها:") # Removed parse_mode
        return RENEW_USER_STATE_DAYS
    except ValueError:
        await update.message.reply_text("❌ معرف تيليجرام غير صالح. يرجى إرسال رقم صحيح.") # Removed parse_mode
        return RENEW_USER_STATE_ID # Stay in the same state to retry

@admin_only
async def renew_user_get_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the number of days and finalizes renewing a user's subscription."""
    try:
        days = int(update.message.text)
        telegram_id = context.user_data['renew_user_telegram_id']
        
        if days <= 0:
            await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقمًا موجبًا.") # Removed parse_mode
            return RENEW_USER_STATE_DAYS # Stay in the same state to retry
        
        if db_manager.renew_subscription(telegram_id, days):
            user = db_manager.get_user(telegram_id)
            await update.message.reply_text(f"✅ تم تجديد اشتراك المستخدم {telegram_id} لـ {days} أيام. تاريخ الانتهاء الجديد: {user.subscription_end_date}") # Removed parse_mode
        else:
            await update.message.reply_text(f"❌ فشل تجديد اشتراك المستخدم {telegram_id}. ربما المستخدم غير موجود.") # Removed parse_mode
        
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ عدد الأيام غير صالح. يرجى إرسال رقم صحيح.") # Removed parse_mode
        return RENEW_USER_STATE_DAYS # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error renewing user subscription: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء تجديد الاشتراك: {e}") # Removed parse_mode
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def cancel_admin_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current admin conversation."""
    await update.message.reply_text("تم إلغاء العملية.", reply_markup=ReplyKeyboardRemove()) # Removed parse_mode
    context.user_data.clear()
    return ConversationHandler.END

# --- Other Admin Commands (already implemented as single-step) ---

@admin_only
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all users."""
    users = db_manager.get_all_users()
    if not users:
        await update.message.reply_text("لا يوجد مشتركين حاليًا.") # Removed parse_mode
        return

    message = "📋 قائمة المشتركين:\n\n"
    for user in users:
        status = "نشط" if db_manager.is_user_subscribed(user) else "منتهي"
        end_date = user.subscription_end_date.strftime("%Y-%m-%d") if user.subscription_end_date else "لا يوجد"
        api_key_status = "محدد" if user.tempmail_api_key else "غير محدد"
        
        message += (
            f"- ID: {user.telegram_id}\n"
            f"  الحالة: {status}\n"
            f"  ينتهي في: {end_date}\n"
            f"  مفتاح API: {api_key_status}\n"
            f"  حسابات تم إنشاؤها: {user.businesses_created_count}\n\n"
        )
    
    await update.message.reply_text(message) # Removed parse_mode

