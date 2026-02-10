import logging
from typing import Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import get_config
from app.services.db import get_supabase
from app.services.dvnet import DVNetClient, DVNetError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

supabase = None
dvnet = None
config = {}


def _init_runtime() -> None:
    global supabase, dvnet, config
    if not config:
        loaded = get_config()
        config = loaded if isinstance(loaded, dict) else {}
    if supabase is None:
        supabase = get_supabase()
    if dvnet is None:
        dvnet = DVNetClient()


def _business_cfg() -> dict:
    return config.get("business", {}) if isinstance(config, dict) else {}


def _telegram_cfg() -> dict:
    return config.get("telegram", {}) if isinstance(config, dict) else {}


def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Add Cash"), KeyboardButton("💰 Balance")],
            [KeyboardButton("🔍 Search")],
            [KeyboardButton("👥 Invite"), KeyboardButton("ℹ️ About Us")],
            [KeyboardButton("💬 Feedback"), KeyboardButton("🎧 Support")],
        ],
        resize_keyboard=True,
    )


def _find_referral_arg(context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    if context.args and context.args[0].isdigit():
        return int(context.args[0])
    return None


def _ensure_user_record(user_id: int, referred_by: Optional[int] = None) -> dict:
    existing = supabase.table("users").select("*").eq("user_id", user_id).execute().data
    if existing:
        user = existing[0]
        if not user.get("tron_address"):
            address = dvnet.get_or_create_deposit_address(str(user_id))
            supabase.table("users").update({"tron_address": address}).eq("user_id", user_id).execute()
            user["tron_address"] = address
        return user

    address = dvnet.get_or_create_deposit_address(str(user_id))
    payload = {
        "user_id": user_id,
        "referred_by": referred_by,
        "tron_address": address,
        "balance": 0,
    }
    supabase.table("users").upsert(payload, on_conflict="user_id").execute()
    return payload


async def perform_search(update: Update, query: str) -> None:
    res = supabase.table("books").select("*").eq("is_sold", False).execute()
    matches = []
    book_price = float(_business_cfg().get("book_price", 0))

    for book in res.data:
        segments = book.get("full_code_string", "").split(",")
        if len(segments) >= 12 and query.lower() in segments[11].lower():
            matches.append(
                f"📖 **{segments[11]}**\nPrice: {book_price} USDT\nBuy: `/buy_{book['id']}`"
            )

    message = "\n\n".join(matches[:5]) if matches else "❌ No books found matching that name."
    await update.message.reply_text(message, parse_mode="Markdown")


async def buy_item(update: Update, book_id: str) -> None:
    uid = update.effective_user.id
    user = _ensure_user_record(uid)
    book = supabase.table("books").select("*").eq("id", book_id).single().execute().data
    business = _business_cfg()
    book_price = float(business.get("book_price", 0))
    referral_percent = float(business.get("referral_percent", 0))

    if not book or book.get("is_sold"):
        await update.message.reply_text("❌ This item is no longer available.")
        return

    if float(user.get("balance", 0)) < book_price:
        await update.message.reply_text("❌ Insufficient balance.")
        return

    new_balance = float(user.get("balance", 0)) - book_price
    supabase.table("users").update({"balance": new_balance}).eq("user_id", uid).execute()
    supabase.table("books").update({"is_sold": True}).eq("id", book_id).execute()

    referred_by = user.get("referred_by")
    if referred_by:
        bonus = book_price * referral_percent
        ref = supabase.table("users").select("balance").eq("user_id", referred_by).single().execute().data
        if ref:
            supabase.table("users").update({"balance": float(ref.get("balance", 0)) + bonus}).eq(
                "user_id", referred_by
            ).execute()

    first_code = str(book.get("full_code_string", "")).split(",")[0]
    await update.message.reply_text(f"✅ Purchased!\nCode: `{first_code}`", parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    ref = _find_referral_arg(context)
    try:
        _ensure_user_record(uid, ref)
    except DVNetError:
        logger.exception("Failed to initialize user %s", uid)
        await update.message.reply_text("❌ We could not create your deposit wallet right now. Please try again shortly.")
        return
    except Exception:
        logger.exception("Unexpected startup failure for user %s", uid)
        await update.message.reply_text("❌ Temporary server issue. Please try again shortly.")
        return

    await update.message.reply_text("🏠 Home", reply_markup=get_main_menu())


async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    txt = update.message.text.strip()
    uid = update.effective_user.id

    try:
        if txt.startswith("/buy_"):
            await buy_item(update, txt.split("_", maxsplit=1)[1])
            return

        if txt == "🔍 Search":
            context.user_data["state"] = "SEARCH"
            await update.message.reply_text("🔎 Type the name of the book:")
            return

        if txt == "➕ Add Cash":
            user = _ensure_user_record(uid)
            await update.message.reply_text(f"📥 Send TRC20 USDT to:\n{user.get('tron_address', 'Unavailable')}")
            return

        if txt == "💰 Balance":
            user = _ensure_user_record(uid)
            await update.message.reply_text(f"💳 Balance: {user.get('balance', 0)} USDT")
            return

        if txt == "👥 Invite":
            business = _business_cfg()
            telegram_cfg = _telegram_cfg()
            referral = float(business.get("referral_percent", 0)) * 100
            bot_username = telegram_cfg.get("bot_username", "")
            link = (
                f"https://t.me/{bot_username}?start={uid}"
                if bot_username
                else "Set telegram.bot_username in config.yaml to enable invite links."
            )
            await update.message.reply_text(f"🎁 Referral Bonus: {referral:.0f}%\n\nYour Invite Link:\n{link}")
            return

        if txt == "ℹ️ About Us":
            about_text = _business_cfg().get("about_us", "We sell digital books with instant delivery.")
            await update.message.reply_text(about_text)
            return

        if txt == "💬 Feedback":
            feedback_contact = _business_cfg().get("feedback_contact", "@your_feedback_username")
            await update.message.reply_text(f"💬 Share feedback here: {feedback_contact}")
            return

        if txt == "🎧 Support":
            support_contact = _business_cfg().get("support_contact", "@your_support_username")
            await update.message.reply_text(f"🎧 Support: {support_contact}")
            return

        if context.user_data.get("state") == "SEARCH":
            context.user_data["state"] = None
            await perform_search(update, txt)
            return

        await update.message.reply_text("❓ I didn't recognize that command. Opening menu...", reply_markup=get_main_menu())
    except DVNetError:
        logger.exception("DV.net issue for user %s", uid)
        await update.message.reply_text("❌ Wallet service temporarily unavailable. Please try again.")
    except Exception:
        logger.exception("Failed handling message for user %s: %s", uid, txt)
        await update.message.reply_text("❌ Something went wrong while processing that. Please try again.")


def main() -> None:
    _init_runtime()
    token = _telegram_cfg().get("token")
    if not token:
        raise RuntimeError("Missing telegram.token in config.yaml")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, handle_msg))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
