import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================
# Bot Configuration
# ==========================

BOT_TOKEN = os.getenv("8707381128:AAHqM_3eXpJofrDHoNjbkQ509F9RT5EvT1s", "").strip()

OWNER_ID = int(os.getenv("8753552605", "0"))

# ==========================
# Storage
# ==========================

DATA_FILE = "channels.json"

# ==========================
# Messages
# ==========================

WELCOME_TEXT = """
👋 <b>Welcome to Auto Forward Bot</b>

This bot automatically forwards every new post from your <b>Main Channel</b>
to all of its duplicate channels.

<b>Features:</b>

✅ Unlimited Main Channels
✅ Unlimited Duplicate Channels
✅ Unlimited Groups
✅ Automatic Forwarding
✅ No Database Required

Choose an option below.
"""

SEND_MAIN_CHANNEL_TEXT = """
📢 <b>Send Main Channel Chat ID</b>

Example:

<code>-1001234567890</code>

After sending the Main Channel ID, the bot will ask you to send duplicate
channel IDs one by one.

When finished, send:

<code>done</code>
"""

ADD_BOT_TEXT = """
⚠️ Before setup:

1. Add the bot as <b>Administrator</b>.
2. Give all permissions.
3. Add the bot to:
   • Main Channel
   • Duplicate Channels
   • Groups (Optional)

Then continue the setup.
"""

SETUP_COMPLETE = """
✅ Setup Completed Successfully.

The bot is now monitoring your Main Channel.

Every new post will automatically be forwarded to all linked channels.
"""

INVALID_CHAT_ID = "❌ Invalid Chat ID."

NOT_ADMIN = """
❌ I am not an administrator in this channel.

Please make me Admin first.
"""

ALREADY_EXISTS = "⚠️ This channel is already added."

REMOVED = "✅ Removed Successfully."

CANCELLED = "❌ Setup Cancelled."

NO_CHANNELS = "No channels configured."

# ==========================
# States
# ==========================

STATE_NONE = 0
STATE_WAIT_MAIN = 1
STATE_WAIT_DUPLICATES = 2

# ==========================
# Logging
# ==========================

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
