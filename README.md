# telegram-project

Telegram book shop bot with Supabase persistence and DV.net deposit wallet integration.

## Project structure

- `main.py` - Telegram bot entrypoint.
- `webhook.py` - DV.net webhook receiver (credits user balances on confirmed deposits).
- `app/telegram_bot.py` - Telegram UI and command handling.
- `app/services/dvnet.py` - DV.net wallet API client.
- `app/services/db.py` - Shared Supabase client.
- `app/config.py` - Shared `config.yaml` loader.

This separates Telegram logic and DV.net logic into different modules so each can be updated independently.

## Configuration

Create `config.yaml` in the project root:

```yaml
telegram:
  token: "<telegram_bot_token>"
  bot_username: "ultimateshop_a_bot"

supabase:
  url: "https://<project>.supabase.co"
  key: "<service_role_or_anon_key>"

server:
  dv_api_key: "<dv_api_key>"
  dv_base_url: "http://127.0.0.1"

business:
  book_price: 5
  referral_percent: 0.05
  about_us: "UltimateShop sells premium digital books."
  feedback_contact: "@your_feedback_username"
  support_contact: "@your_support_username"
```

## Setup on Ubuntu (Evoxt)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd /workspace/telegram-project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run services

Run bot polling:

```bash
source .venv/bin/activate
python main.py
```

Run webhook API (separate process):

```bash
source .venv/bin/activate
python webhook.py
```

## What was fixed

- User records are now guaranteed (`_ensure_user_record`) before balance/add-cash operations.
- TRC20 address is generated and saved if missing.
- Add Cash now always returns a real wallet address (no more `None`).
- Button commands for Invite, About Us, Feedback, and Support are explicitly handled.
- Search state no longer incorrectly hijacks menu button presses.
- Webhook validates payload and updates balances safely.

## Updating safely

1. Pull new code.
2. Update `config.yaml` values if needed.
3. Restart both bot and webhook services.
4. Test in Telegram:
   - `/start`
   - `➕ Add Cash`
   - `💰 Balance`
   - `👥 Invite`
   - `ℹ️ About Us`
   - `💬 Feedback`
   - `🎧 Support`

If one response is wrong, check the corresponding module in `app/telegram_bot.py` or `app/services/dvnet.py`.
