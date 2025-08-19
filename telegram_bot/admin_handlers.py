# facebook_business_bot/telegram_bot/admin_handlers.py
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from config import ADMIN_ID
from database.db_manager import db_manager
from utils.helpers import escape_markdown_v2

logger = logging.getLogger(__name__)

# --- Admin Check Decorator ---
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ عذرًا، هذا الأمر مخصص للمسؤولين فقط.")
            logger.warning(f"Non-admin user {update.effective_user.id} tried to access admin command: {func.__name__}")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# --- Admin Commands ---

@admin_only
async def admin_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the admin menu."""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مشترك", callback_data="admin_add_user")],
        [InlineKeyboardButton("➖ حذف مشترك", callback_data="admin_delete_user")],
        [InlineKeyboardButton("📋 قائمة المشتركين", callback_data="admin_list_users")],
        [InlineKeyboardButton("✉️ إرسال رسالة للكل", callback_data="admin_send_message_to_all")],
        [InlineKeyboardButton("🎁 مكافأة المشتركين", callback_data="admin_reward_users")],
        [InlineKeyboardButton("🔄 تجديد اشتراك مستخدم", callback_data="admin_renew_user_subscription")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لوحة تحكم المسؤول:", reply_markup=reply_markup)

@admin_only
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to add a new user."""
    # Expected format: /add_user <telegram_id> <api_key> <subscription_days>
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "❌ استخدام خاطئ. الاستخدام الصحيح: `/add_user <معرف_تيليجرام> <مفتاح_API_للبريد_المؤقت> <عدد_أيام_الاشتراك>`",
            parse_mode='MarkdownV2'
        )
        return

    try:
        telegram_id = int(args[0])
        api_key = args[1]
        subscription_days = int(args[2])

        user = db_manager.get_user(telegram_id)
        if user:
            await update.message.reply_text(f"⚠️ المستخدم `{telegram_id}` موجود بالفعل. جاري تحديث بياناته.")
            user.tempmail_api_key = api_key
            user.subscription_end_date = date.today() + timedelta(days=subscription_days)
            db_manager.update_user(user)
            await update.message.reply_text(f"✅ تم تحديث بيانات المستخدم `{telegram_id}` بنجاح.")
        else:
            new_user = db_manager.add_user(telegram_id, is_admin=False, tempmail_api_key=api_key, subscription_days=subscription_days)
            if new_user:
                await update.message.reply_text(f"✅ تم إضافة المستخدم `{telegram_id}` بنجاح. تاريخ انتهاء الاشتراك: `{new_user.subscription_end_date}`")
            else:
                await update.message.reply_text(f"❌ فشل إضافة المستخدم `{telegram_id}`.")
    except ValueError:
        await update.message.reply_text("❌ معرف تيليجرام أو عدد الأيام غير صالح. يجب أن يكون أرقامًا صحيحة.")
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء إضافة المستخدم: {escape_markdown_v2(str(e))}")

@admin_only
async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to delete a user."""
    # Expected format: /delete_user <telegram_id>
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "❌ استخدام خاطئ. الاستخدام الصحيح: `/delete_user <معرف_تيليجرام>`",
            parse_mode='MarkdownV2'
        )
        return

    try:
        telegram_id = int(args[0])
        user_to_delete = db_manager.get_user(telegram_id)
        if not user_to_delete:
            await update.message.reply_text(f"⚠️ المستخدم `{telegram_id}` غير موجود.")
            return
        
        if db_manager.delete_user(telegram_id):
            await update.message.reply_text(f"✅ تم حذف المستخدم `{telegram_id}` بنجاح.")
        else:
            await update.message.reply_text(f"❌ فشل حذف المستخدم `{telegram_id}`.")
    except ValueError:
        await update.message.reply_text("❌ معرف تيليجرام غير صالح. يجب أن يكون رقمًا صحيحًا.")
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء حذف المستخدم: {escape_markdown_v2(str(e))}")

@admin_only
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all users."""
    users = db_manager.get_all_users()
    if not users:
        await update.message.reply_text("لا يوجد مشتركين حاليًا.")
        return

    message = "📋 *قائمة المشتركين:*\n\n"
    for user in users:
        status = "نشط" if db_manager.is_user_subscribed(user) else "منتهي"
        end_date = user.subscription_end_date.strftime("%Y-%m-%d") if user.subscription_end_date else "لا يوجد"
        api_key_status = "محدد" if user.tempmail_api_key else "غير محدد"
        
        message += (
            f"\\- ID: `{escape_markdown_v2(str(user.telegram_id))}`\n"
            f"  الحالة: *{escape_markdown_v2(status)}*\n"
            f"  ينتهي في: `{escape_markdown_v2(end_date)}`\n"
            f"  مفتاح API: *{escape_markdown_v2(api_key_status)}*\n"
            f"  حسابات تم إنشاؤها: `{escape_markdown_v2(str(user.businesses_created_count))}`\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='MarkdownV2')

@admin_only
async def send_message_to_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to send a message to all users."""
    # Expected format: /send_message_to_all <your message here>
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("❌ يرجى تقديم الرسالة التي تريد إرسالها.")
        return

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
    
    await update.message.reply_text(f"✅ تم إرسال الرسالة إلى {sent_count} مستخدم. فشل إرسالها إلى {failed_count} مستخدم.")

@admin_only
async def reward_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to reward all users with extra subscription days."""
    # Expected format: /reward_users <days>
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "❌ استخدام خاطئ. الاستخدام الصحيح: `/reward_users <عدد_الأيام>`",
            parse_mode='MarkdownV2'
        )
        return

    try:
        days = int(args[0])
        if days <= 0:
            await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقمًا موجبًا.")
            return
        
        updated_count = db_manager.reward_all_users(days)
        await update.message.reply_text(f"✅ تم مكافأة {updated_count} مستخدمًا بـ {days} أيام إضافية.")
    except ValueError:
        await update.message.reply_text("❌ عدد الأيام غير صالح. يجب أن يكون رقمًا صحيحًا.")
    except Exception as e:
        logger.error(f"Error rewarding users: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء مكافأة المستخدمين: {escape_markdown_v2(str(e))}")

@admin_only
async def renew_user_subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to renew a specific user's subscription."""
    # Expected format: /renew_user_subscription <telegram_id> <days>
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "❌ استخدام خاطئ. الاستخدام الصحيح: `/renew_user_subscription <معرف_تيليجرام> <عدد_الأيام>`",
            parse_mode='MarkdownV2'
        )
        return

    try:
        telegram_id = int(args[0])
        days = int(args[1])
        if days <= 0:
            await update.message.reply_text("❌ عدد الأيام يجب أن يكون رقمًا موجبًا.")
            return
        
        if db_manager.renew_subscription(telegram_id, days):
            user = db_manager.get_user(telegram_id)
            await update.message.reply_text(f"✅ تم تجديد اشتراك المستخدم `{telegram_id}` لـ {days} أيام. تاريخ الانتهاء الجديد: `{user.subscription_end_date}`")
        else:
            await update.message.reply_text(f"❌ فشل تجديد اشتراك المستخدم `{telegram_id}`. ربما المستخدم غير موجود.")
    except ValueError:
        await update.message.reply_text("❌ معرف تيليجرام أو عدد الأيام غير صالح. يجب أن يكون أرقامًا صحيحة.")
    except Exception as e:
        logger.error(f"Error renewing user subscription: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء تجديد الاشتراك: {escape_markdown_v2(str(e))}")

