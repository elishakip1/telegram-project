import yaml
import re
import requests
import logging
from supabase import create_client, Client
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- INITIALIZATION ---
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

supabase: Client = create_client(config['supabase']['url'], config['supabase']['key'])

# --- DV.NET SYNC LOGIC ---
def sync_user_balance(user_id):
    """
    Asks DV.net for the latest balance of the user's sticky wallet.
    Updates Supabase if the balance has increased.
    """
    try:
        # Endpoint to check external wallet status by user ID
        url = f"http://localhost/api/v1/external/wallet/{user_id}"
        headers = {"x-api-key": config['server']['dv_api_key']}
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            data = r.json().get('data', r.json())
            # Native DV.net usually returns 'balance' or 'confirmed_balance'
            current_onchain_balance = float(data.get('balance', 0.0))
            
            # Update Supabase balance to match the on-chain deposit
            supabase.table("users").update({"balance": current_onchain_balance}).eq("user_id", user_id).execute()
            return current_onchain_balance
    except Exception as e:
        print(f"Sync Error: {e}")
    return None

# --- UI MENU ---
def get_main_menu():
    buttons = [
        [KeyboardButton("➕ Add Cash"), KeyboardButton("💰 Balance")],
        [KeyboardButton("🔍 Search")],
        [KeyboardButton("👥 Invite"), KeyboardButton("ℹ️ About Us")],
        [KeyboardButton("💬 Feedback"), KeyboardButton("🎧 Support")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# --- SEARCH & PURCHASE LOGIC ---
async def perform_search(update, query):
    """Checks Index 11 (Row 12) for the book name."""
    res = supabase.table("books").select("*").eq("is_sold", False).execute()
    matches = []
    
    for book in res.data:
        segments = book['full_code_string'].split(',')
        if len(segments) >= 12 and query.lower() in segments[11].lower():
            # In your format, segments[0] is the access code
            matches.append({
                "name": segments[11],
                "code": segments[0],
                "db_id": book['id']
            })

    if matches:
        for m in matches[:3]:
            # We show a "Buy" message for the search result
            await update.message.reply_text(
                f"📖 **Book Found:** {m['name']}\n💰 **Price:** {config['business']['book_price']} USDT\n\n"
                f"To buy this code, type: `/buy_{m['db_id']}`", 
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text("❌ No books found. Try a different keyword.")

# --- HANDLERS ---
async def handle_everything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "💰 Balance":
        # First, sync with DV.net to see if they just deposited
        new_bal = sync_user_balance(user_id)
        await update.message.reply_text(f"💳 **Current Balance:** {new_bal if new_bal is not None else 'Check Supabase'} USDT", parse_mode='Markdown')

    elif text == "🔍 Search":
        await update.message.reply_text("🔎 Enter book name:")
        context.user_data['state'] = 'SEARCHING'

    elif context.user_data.get('state') == 'SEARCHING':
        await perform_search(update, text)
        context.user_data['state'] = None

    elif text.startswith("/buy_"):
        await process_purchase(update, text.split('_')[1])

    else:
        await update.message.reply_text("🏠 **Home Menu**", reply_markup=get_main_menu())

async def process_purchase(update, book_id):
    user_id = update.effective_user.id
    price = config['business']['book_price']
    
    # 1. Get user balance and referrer
    user_res = supabase.table("users").select("*").eq("user_id", user_id).single().execute()
    user_data = user_res.data
    
    if float(user_data['balance']) < price:
        await update.message.reply_text(f"⚠️ Insufficient funds! You need {price} USDT. Tap 'Add Cash'.")
        return

    # 2. Get the book code
    book_res = supabase.table("books").select("*").eq("id", book_id).single().execute()
    book_data = book_res.data
    
    # 3. TRANSACTION (Deduct balance, Mark sold, Pay Referrer)
    new_balance = float(user_data['balance']) - price
    supabase.table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()
    supabase.table("books").update({"is_sold": True}).eq("id", book_id).execute()

    # 4. Pay Referrer (5%)
    if user_data['referred_by']:
        bonus = price * config['business']['referral_percent']
        # Fetch referrer balance
        ref_res = supabase.table("users").select("balance").eq("user_id", user_data['referred_by']).single().execute()
        new_ref_bal = float(ref_res.data['balance']) + bonus
        supabase.table("users").update({"balance": new_ref_bal}).eq("user_id", user_data['referred_by']).execute()

    await update.message.reply_text(f"🎉 **Purchase Successful!**\n\nYour Access Code:\n`{book_data['full_code_string'].split(',')[0]}`", parse_mode='Markdown')