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

# --- CONFIG ---
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

supabase: Client = create_client(config['supabase']['url'], config['supabase']['key'])

# --- MENU UI ---
def get_main_menu():
    # Exactly as requested: [add cash, balance\n search \n invite, about us, feedback, support]
    buttons = [
        [KeyboardButton("➕ Add Cash"), KeyboardButton("💰 Balance")],
        [KeyboardButton("🔍 Search")],
        [KeyboardButton("👥 Invite"), KeyboardButton("ℹ️ About Us")],
        [KeyboardButton("💬 Feedback"), KeyboardButton("🎧 Support")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# --- SAFE DV.NET CALL ---
def get_address_safe(user_id):
    try:
        url = f"http://localhost/api/v1/external/wallet"
        headers = {"x-api-key": config['server']['dv_api_key'], "Content-Type": "application/json"}
        payload = {"amount": 0, "store_external_id": str(user_id), "currency": "USDT_TRC20"}
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        matches = re.findall(r'T[A-Za-z0-9]{33}', r.text)
        return next((m for m in matches if len(m) == 34), "Address Pending")
    except:
        return "Address Pending (Check later)"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    # Send immediate "Home" message so user sees buttons right away
    await update.message.reply_text("🏠 **Home**", reply_markup=get_main_menu(), parse_mode='Markdown')

    # Then try database sync in the background
    try:
        address = get_address_safe(user_id)
        supabase.table("users").upsert({
            "user_id": user_id,
            "referred_by": ref_id,
            "tron_address": address
        }, on_conflict="user_id").execute()
    except Exception as e:
        logger.error(f"Database sync failed: {e}")

async def handle_everything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    This is your Failure Point. 
    Any text that isn't a known command or button takes them HOME.
    """
    text = update.message.text
    user_id = update.effective_user.id

    if text == "💰 Balance":
        try:
            res = supabase.table("users").select("balance").eq("user_id", user_id).single().execute()
            bal = res.data.get('balance', 0.0)
            await update.message.reply_text(f"💳 **Balance:** {bal} USDT", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Balance currently unavailable.")

    elif text == "➕ Add Cash":
        try:
            res = supabase.table("users").select("tron_address").eq("user_id", user_id).single().execute()
            addr = res.data.get('tron_address', "T...")
            await update.message.reply_text(f"📥 Deposit TRC20 USDT to:\n`{addr}`", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Payment system offline.")

    elif text == "🔍 Search":
        await update.message.reply_text("🔎 Type the name of the book you want to find:")
        context.user_data['state'] = 'SEARCHING'

    elif context.user_data.get('state') == 'SEARCHING':
        # (Insert your search logic here)
        context.user_data['state'] = None
        await update.message.reply_text("🏠 Returned to Home.", reply_markup=get_main_menu())

    else:
        # THE CATCH-ALL: Returns them Home for any random word or command
        await update.message.reply_text("🏠 **Home Menu**", reply_markup=get_main_menu(), parse_mode='Markdown')

# --- RUNNER ---
if __name__ == "__main__":
    application = Application.builder().token(config['telegram']['token']).build()
    
    # 1. Handle /start
    application.add_handler(CommandHandler("start", start))
    
    # 2. Handle everything else (Text, Commands, unrecognized words)
    application.add_handler(MessageHandler(filters.ALL, handle_everything))
    
    application.run_polling(drop_pending_updates=True)