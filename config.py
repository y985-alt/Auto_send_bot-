import os
import logging
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ======================================================
# Telegram Bot
# ======================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in .env")

# ======================================================
# Database
# ======================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing in .env")

# ======================================================
# Owner
# ======================================================

try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except ValueError:
    OWNER_ID = 0

if OWNER_ID == 0:
    raise ValueError("OWNER_ID is missing or invalid in .env")

# ======================================================
# Logging
# ======================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT
)

logger = logging.getLogger("AutoForwardBot")

# ======================================================
# Bot Information
# ======================================================

BOT_NAME = "Auto Forward Bot"
BOT_VERSION = "1.0.0"

# ======================================================
# Messages
# ======================================================

WELCOME_MESSAGE = (
    "👋 Welcome!\n\n"
    "I can automatically copy posts from your Main Channel "
    "to unlimited destination Channels or Groups.\n\n"
    "Choose an option below to start setup."
)

NOT_OWNER = "❌ You are not authorized to use this bot."

SOURCE_ADDED = "✅ Main channel saved successfully."

DESTINATION_ADDED = "✅ Destination saved successfully."

SOURCE_EXISTS = "⚠️ This main channel is already added."

DESTINATION_EXISTS = "⚠️ This destination is already linked."

INVALID_CHAT = "❌ Invalid Chat ID."

REMOVED = "✅ Removed successfully."

NO_SOURCE = "❌ No source channel found."

NO_DESTINATION = "❌ No destination channel found."

FORWARD_ERROR = "⚠️ Failed to copy message."

SUCCESS = "✅ Done."

CANCELLED = "❌ Cancelled."

# ======================================================
# Limits
# ======================================================

MAX_DESTINATIONS_PER_SOURCE = 1000000

MAX_SOURCES = 1000000

# ======================================================
# Retry Settings
# ======================================================

RETRY_COUNT = 3

RETRY_DELAY = 2

# ======================================================
# Database Table Names
# ======================================================

SOURCE_TABLE = "source_channels"

DESTINATION_TABLE = "destination_channels"

MAPPING_TABLE = "channel_mappings"
