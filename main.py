import yaml
import re
import requests
import logging
from supabase import create_client, Client
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG LOADING ---
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    logger.error("config.yaml not found! Bot cannot start without configuration.")
    exit()

# Initialize Supabase
supabase: Client = create_client(config['supabase']['url'], config['supabase']['key'])

# --- UI COMPONENTS ---
def get_main_menu():
    # Buttons: [add cash, balance\n search \n invite, about us, feedback, support]
    buttons = [
        [KeyboardButton("➕ Add Cash"), KeyboardButton("💰 Balance")],
        [KeyboardButton("🔍 Search")],
        [KeyboardButton("👥 Invite"), KeyboardButton("ℹ️ About Us")],
        [KeyboardButton("💬 Feedback"), KeyboardButton("🎧 Support")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# --- DV.NET LOGIC ---
def get_user_tron_address(user_id):
    # Using localhost because bot and DV.net are on the same server
    url = f"http://localhost/api/v1/external/wallet"
    headers = {"x-api-key": config['server']['dv_api_key'], "Content-Type": "application/json"}
    payload = {"amount": 0, "store_external_id": str(user_id), "currency": "USDT_TRC20"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        # Deep Search regex for Tron address (Starts with T, 34 chars)
        matches = re.findall(r'T[A-Za-z0-9]{33}', r.text)
        return next((m for m in matches if len(m) == 34), None)
    except Exception as e:
        logger.error(f"DV.net API Error: {e}")
        return None

# --- SEARCH LOGIC ---
async def perform_search(update: Update, query: str):
    # Query Supabase for unsold books
    res = supabase.table("books").select("*").eq("is_sold", False).execute()
    matches = []
    
    for book in res.data:
        # SEARCHABLE PLACE IS ROW 12 (Index 11 in comma-separated string)
        segments = book['full_code_string'].split(',')
        if len(segments) >= 12:
            book_name = segments[11].strip()
            if query.lower() in book_name.lower():
                matches.append(f"📖 **{book_name}**\nAccess Code: `{segments[0]}`")

    if matches:
        await update.message.reply_text("\n\n".join(matches[:5]), parse_mode='Markdown', reply_markup=get_main_menu())
    else:
        await update.message.reply_text("❌ No books found matching that name.", reply_markup=get_main_menu())

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Check if user was referred: /start 12345
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    # Generate/Retrieve Sticky Tron Address
    address = get_user_tron_address(user_id)
    
    # Sync with Supabase
    supabase.table("users").upsert({
        "user_id": user_id,
        "referred_by": ref_id,
        "tron_address": address
    }, on_conflict="user_id").execute()

    await update.message.reply_text(
        "👋 Welcome! Your account is active.\nUse the menu to get started.",
        reply_markup=get_main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    state = context.user_data.get('state')

    if text == "💰 Balance":
        res = supabase.table("users").select("balance").eq("user_id", user_id).single().execute()
        balance = res.data.get('balance', 0.0)
        await update.message.reply_text(f"💳 **Balance:** {balance} USDT", parse_mode='Markdown')

    elif text == "➕ Add Cash":
        res = supabase.table("users").select("tron_address").eq("user_id", user_id).single().execute()
        addr = res.data.get('tron_address')
        await update.message.reply_text(f"📥 Send TRC20 USDT to:\n`{addr}`", parse_mode='Markdown')

    elif text == "🔍 Search":
        await update.message.reply_text("🔎 Type the name of the book:")
        context.user_data['state'] = 'SEARCHING'

    elif state == 'SEARCHING':
        await perform_search(update, text)
        context.user_data['state'] = None

    elif text == "👥 Invite":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        await update.message.reply_text(f"🎁 **Referral Bonus:** 5%\n\nYour Invite Link:\n{link}")

    else:
        # FAILURE POINT: Catch-all for unknown input
        await update.message.reply_text("❓ I didn't recognize that command. Opening menu...", reply_markup=get_main_menu())

# --- RUNNER ---
if __name__ == "__main__":
    application = Application.builder().token(config['telegram']['token']).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Failure point for unknown /commands
    application.add_handler(MessageHandler(filters.COMMAND, handle_text))
    
    print("🚀 Bot starting...")
    application.run_polling(drop_pending_updates=True)