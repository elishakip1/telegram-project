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

- User records are guaranteed (`_ensure_user_record`) before balance/add-cash operations.
- TRC20 address is generated and saved if missing.
- Add Cash now returns a real wallet address (no more `None`) or a clear temporary error.
- DV.net wallet response parsing is more reliable (supports JSON and text payload forms).
- Button commands for Invite, About Us, Feedback, and Support are explicitly handled.
- Search state no longer incorrectly hijacks menu button presses.
- Webhook validates status, external ID, and amount before balance updates.

## How to update on your Ubuntu server

From your server shell:

```bash
cd /workspace/telegram-project
git pull
source .venv/bin/activate
pip install -r requirements.txt
```

If you changed `config.yaml`, verify:
- `telegram.token`
- `telegram.bot_username`
- `supabase.url`
- `supabase.key`
- `server.dv_api_key`
- `server.dv_base_url`

Then restart both processes.

### If you run manually in terminal/tmux

Stop old bot/webhook processes and start again:

```bash
cd /workspace/telegram-project
source .venv/bin/activate
python main.py
```

```bash
cd /workspace/telegram-project
source .venv/bin/activate
python webhook.py
```

### If you run with systemd (recommended)

Restart services after each deploy:

```bash
sudo systemctl daemon-reload
sudo systemctl restart telegram-bot
sudo systemctl restart telegram-webhook
sudo systemctl status telegram-bot --no-pager
sudo systemctl status telegram-webhook --no-pager
```

Example unit files:

`/etc/systemd/system/telegram-bot.service`

```ini
[Unit]
Description=Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/workspace/telegram-project
ExecStart=/workspace/telegram-project/.venv/bin/python main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/telegram-webhook.service`

```ini
[Unit]
Description=Telegram DV.net Webhook
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/workspace/telegram-project
ExecStart=/workspace/telegram-project/.venv/bin/python webhook.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable once:

```bash
sudo systemctl enable telegram-bot
sudo systemctl enable telegram-webhook
```


## Important deploy note

Do **not** paste raw Python code directly into the shell prompt.
Use `cat <<'EOF' > filename.py` blocks (as shown in this README) or edit files with `nano`/`vim`, then run them with `python filename.py`.

## Quick post-update checks in Telegram

1. `/start`
2. `➕ Add Cash` (must return a TRC20 address)
3. `💰 Balance`
4. `👥 Invite`
5. `ℹ️ About Us`
6. `💬 Feedback`
7. `🎧 Support`

## If "nothing works" after deploy

Run these checks on Ubuntu server:

```bash
cd /workspace/telegram-project
source .venv/bin/activate
python -m py_compile main.py webhook.py app/config.py app/telegram_bot.py app/services/db.py app/services/dvnet.py
```

If compile is OK, check service logs:

```bash
sudo journalctl -u telegram-bot -n 100 --no-pager
sudo journalctl -u telegram-webhook -n 100 --no-pager
```

Common cause: missing keys in `config.yaml` (especially `business.*` and `telegram.bot_username`).
