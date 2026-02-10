cat <<'EOF' > main.py
import yaml, re, requests, logging
from supabase import create_client, Client
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, filename='bot.log', filemode='a')
logger = logging.getLogger(__name__)

# --- CONFIG ---
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

supabase: Client = create_client(config['supabase']['url'], config['supabase']['key'])

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Add Cash"), KeyboardButton("💰 Balance")],
        [KeyboardButton("🔍 Search")],
        [KeyboardButton("👥 Invite"), KeyboardButton("ℹ️ About Us")],
        [KeyboardButton("💬 Feedback"), KeyboardButton("🎧 Support")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    try:
        url = "http://localhost/api/v1/external/wallet"
        headers = {"x-api-key": config['server']['dv_api_key']}
        payload = {"amount": 0, "store_external_id": str(uid), "currency": "USDT_TRC20"}
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        addr = re.findall(r'T[A-Za-z0-9]{33}', r.text)[0]
    except:
        addr = "Pending... (Click Add Cash)"

    supabase.table("users").upsert({
        "user_id": uid, "referred_by": ref_id, "tron_address": addr
    }, on_conflict="user_id").execute()

    await update.message.reply_text("🏠 **Welcome!**", reply_markup=main_menu(), parse_mode='Markdown')

async def buy(update: Update, book_id: str):
    uid = update.effective_user.id
    price = 20.0
    
    user = supabase.table("users").select("*").eq("user_id", uid).single().execute().data
    book = supabase.table("books").select("*").eq("id", book_id).single().execute().data

    if float(user['balance']) < price:
        return await update.message.reply_text("❌ Low balance.")

    supabase.table("users").update({"balance": float(user['balance']) - price}).eq("user_id", uid).execute()
    supabase.table("books").update({"is_sold": True}).eq("id", book_id).execute()

    if user['referred_by']:
        r_bal = supabase.table("users").select("balance").eq("user_id", user['referred_by']).single().execute().data['balance']
        supabase.table("users").update({"balance": float(r_bal) + 1.0}).eq("user_id", user['referred_by']).execute()

    await update.message.reply_text(f"✅ Success! Code: `{book['full_code_string'].split(',')[0]}`", parse_mode='Markdown')

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    uid = update.effective_user.id
    state = context.user_data.get('state')

    if txt == "💰 Balance":
        res = supabase.table("users").select("balance").eq("user_id", uid).single().execute()
        await update.message.reply_text(f"💳 Balance: {res.data['balance']} USDT")
    elif txt == "➕ Add Cash":
        res = supabase.table("users").select("tron_address").eq("user_id", uid).single().execute()
        await update.message.reply_text(f"📥 Send USDT (TRC20) to:\n`{res.data['tron_address']}`", parse_mode='Markdown')
    elif txt == "🔍 Search":
        await update.message.reply_text("🔎 Book name?")
        context.user_data['state'] = 'SEARCH'
    elif txt == "👥 Invite":
        bot = (await context.bot.get_me()).username
        await update.message.reply_text(f"🎁 Invite & Earn 5%:\nhttps://t.me/{bot}?start={uid}")
    elif txt.startswith("/buy_"):
        await buy(update, txt.split('_')[1])
    elif state == 'SEARCH':
        res = supabase.table("books").select("*").eq("is_sold", False).execute()
        found = [f"📖 {b['full_code_string'].split(',')[11]}\nBuy: `/buy_{b['id']}`" for b in res.data if txt.lower() in b['full_code_string'].split(',')[11].lower()]
        context.user_data['state'] = None
        await update.message.reply_text("\n\n".join(found) if found else "❌ Not found.")
    else:
        await update.message.reply_text("🏠 Home", reply_markup=main_menu())

if __name__ == "__main__":
    app = Application.builder().token(config['telegram']['token']).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling()
EOF
