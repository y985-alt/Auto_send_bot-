import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ==========================
# Bot Configuration
# ==========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ==========================
# Validation
# ==========================

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")
