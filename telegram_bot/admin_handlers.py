# facebook_business_bot/telegram_bot/admin_handlers.py
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown # Keep for reference, but use custom escape_markdown_v2

from config import ADMIN_ID
from database.db_manager import db_manager
from utils.helpers import escape_markdown_v2

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
                await update.message.reply_text(escape_markdown_v2("❌ عذرًا، هذا الأمر مخصص للمسؤولين فقط."), parse_mode='MarkdownV2')
            elif update.callback_query:
                await update.callback_query.answer(escape_markdown_v2("❌ عذرًا، هذا الأمر مخصص للمسؤولين فقط."), show_alert=True)
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
        await update.message.reply_text(escape_markdown_v2("لوحة تحكم المسؤول:"), reply_markup=reply_markup, parse_mode='MarkdownV2')
    elif update.callback_query:
        await update.callback_query.edit_message_text(escape_markdown_v2("لوحة تحكم المسؤول:"), reply_markup=reply_markup, parse_mode='MarkdownV2')

# --- Admin Callback Query Handlers (for starting multi-step commands) ---

@admin_only
async def admin_add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the add user conversation."""
    await update.callback_query.edit_message_text(
        escape_markdown_v2("الرجاء إرسال معرف تيليجرام (Telegram ID) للمشترك الجديد:")
        , parse_mode='MarkdownV2'
    )
    return ADD_USER_STATE_ID

@admin_only
async def admin_delete_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the delete user conversation."""
    await update.callback_query.edit_message_text(
        escape_markdown_v2("الرجاء إرسال معرف تيليجرام (Telegram ID) للمشترك الذي تريد حذفه:")
        , parse_mode='MarkdownV2'
    )
    return DELETE_USER_STATE_ID

@admin_only
async def admin_send_message_to_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the send message to all conversation."""
    await update.callback_query.edit_message_text(
        escape_markdown_v2("الرجاء إرسال الرسالة التي تريد إرسالها لجميع المشتركين:")
        , parse_mode='MarkdownV2'
    )
    return SEND_MESSAGE_STATE

@admin_only
async def admin_reward_users_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the reward users conversation."""
    await update.callback_query.edit_message_text(
        escape_markdown_v2("الرجاء إرسال عدد الأيام التي تريد مكافأة جميع المشتركين بها:")
        , parse_mode='MarkdownV2'
    )
    return REWARD_USERS_STATE_DAYS

@admin_only
async def admin_renew_user_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the renew user subscription conversation."""
    await update.callback_query.edit_message_text(
        escape_markdown_v2("الرجاء إرسال معرف تيليجرام (Telegram ID) للمشترك الذي تريد تجديد اشتراكه:")
        , parse_mode='MarkdownV2'
    )
    return RENEW_USER_STATE_ID

# --- Admin Conversation Step Handlers ---

@admin_only
async def add_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the Telegram ID for adding a user."""
    try:
        telegram_id = int(update.message.text)
        context.user_data['add_user_telegram_id'] = telegram_id
        await update.message.reply_text(escape_markdown_v2("الرجاء إرسال مفتاح TempMail API للمشترك:"), parse_mode='MarkdownV2')
        return ADD_USER_STATE_API_KEY
    except ValueError:
        await update.message.reply_text(escape_markdown_v2("❌ معرف تيليجرام غير صالح. يرجى إرسال رقم صحيح."), parse_mode='MarkdownV2')
        return ADD_USER_STATE_ID # Stay in the same state to retry

@admin_only
async def add_user_get_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the API Key for adding a user."""
    api_key = update.message.text.strip()
    context.user_data['add_user_api_key'] = api_key
    await update.message.reply_text(escape_markdown_v2("الرجاء إرسال عدد أيام الاشتراك:"), parse_mode='MarkdownV2')
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
            await update.message.reply_text(escape_markdown_v2(f"⚠️ المستخدم `{telegram_id}` موجود بالفعل. جاري تحديث بياناته."), parse_mode='MarkdownV2')
            user.tempmail_api_key = api_key
            user.subscription_end_date = date.today() + timedelta(days=subscription_days)
            db_manager.update_user(user)
            await update.message.reply_text(escape_markdown_v2(f"✅ تم تحديث بيانات المستخدم `{telegram_id}` بنجاح. تاريخ انتهاء الاشتراك: `{user.subscription_end_date}`"), parse_mode='MarkdownV2')
        else:
            new_user = db_manager.add_user(telegram_id, is_admin=False, tempmail_api_key=api_key, subscription_days=subscription_days)
            if new_user:
                await update.message.reply_text(escape_markdown_v2(f"✅ تم إضافة المستخدم `{telegram_id}` بنجاح. تاريخ انتهاء الاشتراك: `{new_user.subscription_end_date}`"), parse_mode='MarkdownV2')
            else:
                await update.message.reply_text(escape_markdown_v2(f"❌ فشل إضافة المستخدم `{telegram_id}`."), parse_mode='MarkdownV2')
        
        # Clear user_data and end conversation
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(escape_markdown_v2("❌ عدد الأيام غير صالح. يرجى إرسال رقم صحيح."), parse_mode='MarkdownV2')
        return ADD_USER_STATE_SUB_DAYS # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء إضافة المستخدم: {escape_markdown_v2(str(e))}", parse_mode='MarkdownV2')
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def delete_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the Telegram ID for deleting a user."""
    try:
        telegram_id = int(update.message.text)
        user_to_delete = db_manager.get_user(telegram_id)
        if not user_to_delete:
            await update.message.reply_text(escape_markdown_v2(f"⚠️ المستخدم `{telegram_id}` غير موجود."), parse_mode='MarkdownV2')
            context.user_data.clear()
            return ConversationHandler.END
        
        if db_manager.delete_user(telegram_id):
            await update.message.reply_text(escape_markdown_v2(f"✅ تم حذف المستخدم `{telegram_id}` بنجاح."), parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(escape_markdown_v2(f"❌ فشل حذف المستخدم `{telegram_id}`."), parse_mode='MarkdownV2')
        
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(escape_markdown_v2("❌ معرف تيليجرام غير صالح. يرجى إرسال رقم صحيح."), parse_mode='MarkdownV2')
        return DELETE_USER_STATE_ID # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء حذف المستخدم: {escape_markdown_v2(str(e))}", parse_mode='MarkdownV2')
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
    
    await update.message.reply_text(escape_markdown_v2(f"✅ تم إرسال الرسالة إلى {sent_count} مستخدم. فشل إرسالها إلى {failed_count} مستخدم."), parse_mode='MarkdownV2')
    context.user_data.clear()
    return ConversationHandler.END

@admin_only
async def reward_users_get_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the number of days to reward all users."""
    try:
        days = int(update.message.text)
        if days <= 0:
            await update.message.reply_text(escape_markdown_v2("❌ عدد الأيام يجب أن يكون رقمًا موجبًا."), parse_mode='MarkdownV2')
            return REWARD_USERS_STATE_DAYS # Stay in the same state to retry
        
        updated_count = db_manager.reward_all_users(days)
        await update.message.reply_text(escape_markdown_v2(f"✅ تم مكافأة {updated_count} مستخدمًا بـ {days} أيام إضافية."), parse_mode='MarkdownV2')
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(escape_markdown_v2("❌ عدد الأيام غير صالح. يرجى إرسال رقم صحيح."), parse_mode='MarkdownV2')
        return REWARD_USERS_STATE_DAYS # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error rewarding users: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء مكافأة المستخدمين: {escape_markdown_v2(str(e))}", parse_mode='MarkdownV2')
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def renew_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the Telegram ID for renewing a user's subscription."""
    try:
        telegram_id = int(update.message.text)
        context.user_data['renew_user_telegram_id'] = telegram_id
        await update.message.reply_text(escape_markdown_v2("الرجاء إرسال عدد الأيام التي تريد تجديد الاشتراك بها:"), parse_mode='MarkdownV2')
        return RENEW_USER_STATE_DAYS
    except ValueError:
        await update.message.reply_text(escape_markdown_v2("❌ معرف تيليجرام غير صالح. يرجى إرسال رقم صحيح."), parse_mode='MarkdownV2')
        return RENEW_USER_STATE_ID # Stay in the same state to retry

@admin_only
async def renew_user_get_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the number of days and finalizes renewing a user's subscription."""
    try:
        days = int(update.message.text)
        telegram_id = context.user_data['renew_user_telegram_id']
        
        if days <= 0:
            await update.message.reply_text(escape_markdown_v2("❌ عدد الأيام يجب أن يكون رقمًا موجبًا."), parse_mode='MarkdownV2')
            return RENEW_USER_STATE_DAYS # Stay in the same state to retry
        
        if db_manager.renew_subscription(telegram_id, days):
            user = db_manager.get_user(telegram_id)
            await update.message.reply_text(escape_markdown_v2(f"✅ تم تجديد اشتراك المستخدم `{telegram_id}` لـ {days} أيام. تاريخ الانتهاء الجديد: `{user.subscription_end_date}`"), parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(escape_markdown_v2(f"❌ فشل تجديد اشتراك المستخدم `{telegram_id}`. ربما المستخدم غير موجود."), parse_mode='MarkdownV2')
        
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(escape_markdown_v2("❌ عدد الأيام غير صالح. يرجى إرسال رقم صحيح."), parse_mode='MarkdownV2')
        return RENEW_USER_STATE_DAYS # Stay in the same state to retry
    except Exception as e:
        logger.error(f"Error renewing user subscription: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء تجديد الاشتراك: {escape_markdown_v2(str(e))}", parse_mode='MarkdownV2')
        context.user_data.clear()
        return ConversationHandler.END

@admin_only
async def cancel_admin_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current admin conversation."""
    await update.message.reply_text(escape_markdown_v2("تم إلغاء العملية."), reply_markup=ReplyKeyboardRemove(), parse_mode='MarkdownV2')
    context.user_data.clear()
    return ConversationHandler.END

# --- Other Admin Commands (already implemented as single-step) ---

@admin_only
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all users."""
    users = db_manager.get_all_users()
    if not users:
        await update.message.reply_text(escape_markdown_v2("لا يوجد مشتركين حاليًا."), parse_mode='MarkdownV2')
        return

    message = escape_markdown_v2("📋 *قائمة المشتركين:*\n\n")
    for user in users:
        status = "نشط" if db_manager.is_user_subscribed(user) else "منتهي"
        end_date = user.subscription_end_date.strftime("%Y-%m-%d") if user.subscription_end_date else "لا يوجد"
        api_key_status = "محدد" if user.tempmail_api_key else "غير محدد"
        
        message += (
            escape_markdown_v2(f"\\- ID: `{user.telegram_id}`\n") +
            escape_markdown_v2(f"  الحالة: *{status}*\n") +
            escape_markdown_v2(f"  ينتهي في: `{end_date}`\n") +
            escape_markdown_v2(f"  مفتاح API: *{api_key_status}*\n") +
            escape_markdown_v2(f"  حسابات تم إنشاؤها: `{user.businesses_created_count}`\n\n")
        )
    
    await update.message.reply_text(message, parse_mode='MarkdownV2')

