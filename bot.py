import os
import sys
import json
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

# -------------- CONFIG --------------
API_ID = "36989662"
API_HASH = "7af4e08e89cb46fef559aecb420a7fdd"
BOT_TOKEN = "8707381128:AAHqM_3eXpJofrDHoNjbkQ509F9RT5EvT1s"
CONFIG_FILE = "channels.json"
# ------------------------------------

# Enable logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Client("auto_forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ─────────────────────────────────────────────
# CONFIG FILE HANDLING (No database)
# ─────────────────────────────────────────────

def load_config():
    """Load channels config from JSON file. Returns dict."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {"mappings": []}
    return {"mappings": []}

def save_config(config):
    """Save channels config to JSON file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def is_bot_admin_in_channel(client, chat_id):
    """Check if bot is admin in a channel (simplified check)."""
    try:
        member = client.get_chat_member(chat_id, "me")
        return member.status in ("administrator", "owner")
    except Exception:
        return False

# ─────────────────────────────────────────────
# /START COMMAND — Welcome + Setup
# ─────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    config = load_config()
    count = len(config.get("mappings", []))
    
    welcome_text = (
        f"👋 **Welcome to Auto-Forward Bot!**\n\n"
        f"✅ **Total setups active:** {count}\n\n"
        f"**How it works:**\n"
        f"1️⃣ Add me to your **Main Channel** as Admin\n"
        f"2️⃣ Add me to your **Duplicate Channels** as Admin\n"
        f"3️⃣ Use /setup to link them\n"
        f"4️⃣ Done! Any new post in Main Channel → Auto-forwarded to duplicates\n\n"
        f"**Commands:**\n"
        f"• /setup — Add a new Main → Duplicates mapping\n"
        f"• /status — See all current mappings\n"
        f"• /delete — Remove a mapping\n"
        f"• /reconfigure — Re-run setup for new channels\n\n"
        f"👇 **Add me to your channels & groups:**"
    )
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Channel", url=f"https://t.me/{client.me.username}?startchannel=new"),
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=new")
        ]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons, parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────────
# /SETUP COMMAND — Interactive channel mapping
# ─────────────────────────────────────────────

# Temporary storage for setup state (in-memory, per-user)
setup_states = {}

@app.on_message(filters.command("setup"))
async def setup_command(client, message: Message):
    user_id = message.from_user.id
    setup_states[user_id] = {"step": "awaiting_main_channel"}
    await message.reply_text(
        "📌 **Step 1/3:** Send me the **Main Channel's username or Chat ID**.\n\n"
        "Example: `@my_main_channel` or `-1001234567890`\n\n"
        "💡 Make sure the bot is **Admin** in that channel.",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.text & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def handle_setup_input(client, message: Message):
    """Handle interactive setup flow."""
    user_id = message.from_user.id
    if user_id not in setup_states:
        return
    
    state = setup_states[user_id]
    text = message.text.strip()
    
    if state["step"] == "awaiting_main_channel":
        # Resolve channel
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            elif text.startswith("-100") or text.lstrip("-").isdigit():
                chat = await client.get_chat(int(text))
            else:
                await message.reply_text("❌ Invalid format. Send `@username` or numeric Chat ID.", parse_mode=ParseMode.MARKDOWN)
                return
            
            # Verify bot is admin
            try:
                me = await client.get_me()

member = await client.get_chat_member(
    chat.id,
    me.id
)
                if member.status not in ("administrator", "owner"):
                    await message.reply_text(f"❌ I'm not an admin in **{chat.title}**. Make me admin first!", parse_mode=ParseMode.MARKDOWN)
                    return
            except Exception:
                await message.reply_text(f"❌ Cannot access **{chat.title}**. Add me as admin first!", parse_mode=ParseMode.MARKDOWN)
                return
            
            state["main_chat_id"] = chat.id
            state["main_chat_title"] = chat.title
            state["duplicates"] = []
            state["step"] = "awaiting_duplicate"
            
            await message.reply_text(
                f"✅ **Main Channel:** {chat.title}\n"
                f"**Chat ID:** `{chat.id}`\n\n"
                f"📌 **Step 2/3:** Now send the **Duplicate Channel's** username or Chat ID.\n"
                f"Send one by one. Type `done` when finished.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}\nCheck the channel username/ID and try again.", parse_mode=ParseMode.MARKDOWN)
    
    elif state["step"] == "awaiting_duplicate":
        if text.lower() == "done":
            if not state["duplicates"]:
                await message.reply_text("❌ You must add at least one duplicate channel!", parse_mode=ParseMode.MARKDOWN)
                return
            
            # Save config
            config = load_config()
            
            # Check if main channel already exists
            for mapping in config["mappings"]:
                if mapping["main_chat_id"] == state["main_chat_id"]:
                    # Update duplicates
                    for dup in state["duplicates"]:
                        if dup not in mapping["duplicates"]:
                            mapping["duplicates"].append(dup)
                    save_config(config)
                    
                    dup_list = "\n".join([f"• {d['title']} (`{d['chat_id']}`)" for d in state["duplicates"]])
                    await message.reply_text(
                        f"✅ **Updated!**\n\n"
                        f"**Main:** {state['main_chat_title']}\n"
                        f"**Duplicates added:**\n{dup_list}\n\n"
                        f"New posts will auto-forward now! 🚀",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    del setup_states[user_id]
                    return
            
            # New mapping
            config["mappings"].append({
                "main_chat_id": state["main_chat_id"],
                "main_chat_title": state["main_chat_title"],
                "duplicates": state["duplicates"]
            })
            save_config(config)
            
            dup_list = "\n".join([f"• {d['title']} (`{d['chat_id']}`)" for d in state["duplicates"]])
            await message.reply_text(
                f"✅ **Setup Complete!**\n\n"
                f"**Main Channel:** {state['main_chat_title']} (`{state['main_chat_id']}`)\n"
                f"**Duplicates ({len(state['duplicates'])}):**\n{dup_list}\n\n"
                f"🚀 Any new post in main channel will auto-forward to duplicates!\n\n"
                f"Use /setup again for another main channel.\n"
                f"Use /reconfigure if you want to add more duplicates later.",
                parse_mode=ParseMode.MARKDOWN
            )
            del setup_states[user_id]
            return
        
        # Add duplicate channel
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            elif text.startswith("-100") or text.lstrip("-").isdigit():
                chat = await client.get_chat(int(text))
            else:
                await message.reply_text("❌ Invalid format. Send `@username` or numeric Chat ID.", parse_mode=ParseMode.MARKDOWN)
                return
            
            # Verify bot is admin
            try:
                member = await client.get_chat_member(chat.id, "me")
                if member.status not in ("administrator", "owner"):
                    await message.reply_text(f"❌ I'm not an admin in **{chat.title}**. Make me admin first!", parse_mode=ParseMode.MARKDOWN)
                    return
            except Exception:
                await message.reply_text(f"❌ Cannot access **{chat.title}**. Add me as admin first!", parse_mode=ParseMode.MARKDOWN)
                return
            
            # Check duplicate already in list
            for d in state["duplicates"]:
                if d["chat_id"] == chat.id:
                    await message.reply_text(f"⚠️ **{chat.title}** is already in your duplicates list!", parse_mode=ParseMode.MARKDOWN)
                    return
            
            state["duplicates"].append({
                "chat_id": chat.id,
                "title": chat.title
            })
            
            await message.reply_text(
                f"✅ Added **{chat.title}** to duplicates! (Total: {len(state['duplicates'])})\n\n"
                f"Send another duplicate channel or type `done` to finish.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────────
# /RECONFIGURE — Setup new channels again
# ─────────────────────────────────────────────

@app.on_message(filters.command("reconfigure"))
async def reconfigure_command(client, message: Message):
    """Alias for /setup"""
    await setup_command(client, message)

# ─────────────────────────────────────────────
# /STATUS — Show all mappings
# ─────────────────────────────────────────────

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    config = load_config()
    
    if not config["mappings"]:
        await message.reply_text(
            "📭 **No mappings configured yet.**\n\nUse /setup to add your first channel mapping.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    text = "📋 **Current Channel Mappings:**\n\n"
    for i, mapping in enumerate(config["mappings"], 1):
        text += f"**{i}. Main:** {mapping['main_chat_title']} (`{mapping['main_chat_id']}`)\n"
        text += f"   **→ Duplicates ({len(mapping['duplicates'])}):**\n"
        for dup in mapping["duplicates"]:
            text += f"      • {dup['title']} (`{dup['chat_id']}`)\n"
        text += "\n"
    
    text += f"\n**Total mappings: {len(config['mappings'])}**"
    
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────────
# /DELETE — Remove a mapping
# ─────────────────────────────────────────────

@app.on_message(filters.command("delete"))
async def delete_command(client, message: Message):
    config = load_config()
    
    if not config["mappings"]:
        await message.reply_text("📭 No mappings to delete.")
        return
    
    # Show buttons for each mapping
    buttons = []
    for i, mapping in enumerate(config["mappings"], 1):
        buttons.append([
            InlineKeyboardButton(
                f"{i}. {mapping['main_chat_title']} ({len(mapping['duplicates'])} dupes)",
                callback_data=f"del_{i-1}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    
    await message.reply_text(
        "🗑 **Select a mapping to delete:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex(r"^del_"))
async def delete_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    
    if data == "del_cancel":
        await callback_query.message.edit_text("❌ Deletion cancelled.")
        await callback_query.answer()
        return
    
    index = int(data.split("_")[1])
    config = load_config()
    
    if index >= len(config["mappings"]):
        await callback_query.answer("Invalid selection!")
        return
    
    removed = config["mappings"].pop(index)
    save_config(config)
    
    await callback_query.message.edit_text(
        f"✅ **Deleted:** {removed['main_chat_title']}\n"
        f"Removed {len(removed['duplicates'])} duplicate channel(s).",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer()

# ─────────────────────────────────────────────
# AUTO-FORWARD: New messages in main channel → duplicates
# ─────────────────────────────────────────────

@app.on_message(filters.channel)
async def auto_forward(client, message: Message):
    """When a new message is posted in any channel, check if it's a main channel and forward."""
    config = load_config()
    chat_id = message.chat.id
    
    for mapping in config["mappings"]:
        if mapping["main_chat_id"] == chat_id:
            # This is a main channel — forward to all duplicates
            for dup in mapping["duplicates"]:
                try:
                    await message.copy(
                        chat_id=dup["chat_id"],
                        caption=message.caption if message.caption else None,
                        parse_mode=ParseMode.MARKDOWN if message.caption else None
                    )
                    logging.info(f"✅ Forwarded from {message.chat.title} → {dup['title']}")
                except Exception as e:
                    logging.error(f"❌ Failed to forward to {dup['title']}: {e}")
            break  # Only one mapping per chat_id, avoid duplicate checks

# ─────────────────────────────────────────────
# KEEP ALIVE for Railway (prevent idle)
# ─────────────────────────────────────────────

async def keep_alive():
    """Send a heartbeat every 10 minutes to keep the bot alive."""
    while True:
        await asyncio.sleep(600)  # 10 minutes
        logging.info("🔄 Heartbeat — Bot is alive")

async def main():
    """Start bot and keep-alive task."""
    # Print bot info
    me = await app.get_me()
    logging.info(f"🤖 Bot started: @{me.username}")
    
    # Start keep-alive in background
    asyncio.create_task(keep_alive())
    
    # Keep running
    await asyncio.Event().wait()

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting Bot...")
        app.run()
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped")
    except Exception:
        logging.exception("Fatal Error")
