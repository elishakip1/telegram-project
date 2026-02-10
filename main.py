import yaml, re, requests, logging
from supabase import create_client, Client
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- INIT ---
logging.basicConfig(level=logging.INFO)
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

supabase: Client = create_client(config['supabase']['url'], config['supabase']['key'])

# --- UI ---
def get_main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Add Cash"), KeyboardButton("💰 Balance")],
        [KeyboardButton("🔍 Search")],
        [KeyboardButton("👥 Invite"), KeyboardButton("ℹ️ About Us")],
        [KeyboardButton("💬 Feedback"), KeyboardButton("🎧 Support")]
    ], resize_keyboard=True)

# --- SEARCH & BUY ---
async def perform_search(update, query):
    res = supabase.table("books").select("*").eq("is_sold", False).execute()
    matches = []
    for b in res.data:
        seg = b['full_code_string'].split(',')
        if len(seg) >= 12 and query.lower() in seg[11].lower(): # Row 12 Search
            matches.append(f"📖 **{seg[11]}**\nPrice: {config['business']['book_price']} USDT\nBuy: `/buy_{b['id']}`")
    
    await update.message.reply_text("\n\n".join(matches[:5]) if matches else "❌ No books found.")

async def buy_item(update, book_id):
    uid = update.effective_user.id
    user = supabase.table("users").select("*").eq("user_id", uid).single().execute().data
    book = supabase.table("books").select("*").eq("id", book_id).single().execute().data

    if float(user['balance']) < config['business']['book_price']:
        return await update.message.reply_text("❌ Insufficient Balance.")

    # Transaction Logic
    new_bal = float(user['balance']) - config['business']['book_price']
    supabase.table("users").update({"balance": new_bal}).eq("user_id", uid).execute()
    supabase.table("books").update({"is_sold": True}).eq("id", book_id).execute()

    # Referral Payout (5%)
    if user['referred_by']:
        bonus = config['business']['book_price'] * config['business']['referral_percent']
        ref = supabase.table("users").select("balance").eq("user_id", user['referred_by']).single().execute().data
        supabase.table("users").update({"balance": float(ref['balance']) + bonus}).eq("user_id", user['referred_by']).execute()

    await update.message.reply_text(f"✅ Purchased!\nCode: `{book['full_code_string'].split(',')[0]}`", parse_mode='Markdown')

# --- HANDLERS ---
async def start(update, context):
    uid = update.effective_user.id
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    # Generate DV.net sticky address
    r = requests.post("http://localhost/api/v1/external/wallet", 
                      headers={"x-api-key": config['server']['dv_api_key']}, 
                      json={"amount": 0, "store_external_id": str(uid), "currency": "USDT_TRC20"})
    addr = re.findall(r'T[A-Za-z0-9]{33}', r.text)[0]

    supabase.table("users").upsert({"user_id": uid, "referred_by": ref, "tron_address": addr}, on_conflict="user_id").execute()
    await update.message.reply_text("🏠 Home", reply_markup=get_main_menu())

async def handle_msg(update, context):
    txt = update.message.text
    if txt == "💰 Balance":
        bal = supabase.table("users").select("balance").eq("user_id", update.effective_user.id).single().execute().data['balance']
        await update.message.reply_text(f"💳 Balance: {bal} USDT")
    elif txt == "🔍 Search":
        await update.message.reply_text("🔎 Enter book name:")
        context.user_data['state'] = 'SEARCH'
    elif context.user_data.get('state') == 'SEARCH':
        await perform_search(update, txt)
        context.user_data['state'] = None
    elif txt.startswith("/buy_"):
        await buy_item(update, txt.split('_')[1])
    else:
        await update.message.reply_text("🏠 Home", reply_markup=get_main_menu())

if __name__ == "__main__":
    app = Application.builder().token(config['telegram']['token']).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, handle_msg))
    app.run_polling(drop_pending_updates=True)