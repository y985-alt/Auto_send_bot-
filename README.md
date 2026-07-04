# 🤖 Telegram Auto-Forward Bot

A powerful Telegram bot that automatically forwards posts from a main channel to multiple duplicate channels. No database required — everything stored in a simple JSON config file.

## ✨ Features

- **Auto-Forward** — New posts in Main Channel → instantly forwarded to all duplicates
- **Multiple Mappings** — Support multiple main channels, each with their own duplicate channels
- **No Database** — Uses `channels.json` file, restart-safe
- **Interactive Setup** — Simple /setup command to configure everything
- **Admin Check** — Verifies bot is admin before allowing configuration

## 🚀 Deploy on Railway

### Prerequisites
1. **Telegram Bot Token** — Get from [@BotFather](https://t.me/BotFather)
2. **API ID & API Hash** — Get from [my.telegram.org](https://my.telegram.org)

### Quick Deploy

1. Fork this repo to your GitHub
2. Go to [Railway.app](https://railway.app)
3. Click **New Project → Deploy from GitHub repo**
4. Select your forked repo
5. Add these **Environment Variables** in Railway:
   - `API_ID` — Your API ID from my.telegram.org
   - `API_HASH` — Your API Hash from my.telegram.org  
   - `BOT_TOKEN` — Your bot token from BotFather
6. Deploy! ✅

## 📱 Usage

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with add-to-channel/group buttons |
| `/setup` | Interactive setup: add main channel + duplicates |
| `/status` | View all current mappings |
| `/delete` | Delete a mapping |
| `/reconfigure` | Same as /setup — add new channels |

## 🔧 Local Development

```bash
git clone https://github.com/YOUR_USERNAME/forward-bot.git
cd forward-bot
pip install -r requirements.txt
export API_ID=your_api_id
export API_HASH=your_api_hash
export BOT_TOKEN=your_bot_token
python bot.py
