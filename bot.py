import os
import json
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

API_ID = 36989662
API_HASH = "7af4e08e89cb46fef559aecb420a7fdd"
BOT_TOKEN = "8707381128:AAHqM_3eXpJofrDHoNjbkQ509F9RT5EvT1s"
CONFIG_FILE = "channels.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Client("auto_forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"mappings": []}
    return {"mappings": []}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

setup_states = {}

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    if not message.from_user:
        return
    c = load_config()
    count = len(c.get("mappings", []))
    txt = (
        f"👋 **Welcome to Auto-Forward Bot!**\n\n"
        f"✅ **Active setups:** {count}\n\n"
        f"**Commands:**\n"
        f"• /setup — Add channel mapping\n"
        f"• /status — View all mappings\n"
        f"• /delete — Remove a mapping\n"
        f"• /reconfigure — Re-run setup\n\n"
        f"**⚠️ Bot ko channel ka Admin banayein!**"
    )
    await message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("setup"))
async def setup_handler(client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    setup_states[uid] = {"step": "awaiting_main"}
    await message.reply_text(
        "📌 **Step 1/3:** Send **Main Channel Chat ID**\n\n"
        "Example: `-1003928300495`\n\n"
        "⚠️ Bot ko **Admin** banayein channel mein!",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command("reconfigure"))
async def reconfigure_handler(client, message: Message):
    if not message.from_user:
        return
    await setup_handler(client, message)

@app.on_message(filters.text & filters.private & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def text_handler(client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    if uid not in setup_states:
        return
    state = setup_states[uid]
    text = message.text.strip()
    config = load_config()

    if state["step"] == "awaiting_main":
        try:
            if not text.startswith("-100"):
                await message.reply_text("❌ Sirf `-100` se shuru Chat ID daalein!", parse_mode=ParseMode.MARKDOWN)
                return
            chat = await client.get_chat(int(text))
            state["main_id"] = chat.id
            state["main_title"] = chat.title
            state["dups"] = []
            state["step"] = "awaiting_dup"
            await message.reply_text(
                f"✅ **Main Channel:** {chat.title}\n\n"
                "📌 **Step 2/3:** Ab **Duplicate Channel Chat ID** bhejein.\n"
                "Type `done` jab sab ho jaye.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ **Error:** {e}", parse_mode=ParseMode.MARKDOWN)
            if uid in setup_states:
                del setup_states[uid]
        return

    if state["step"] == "awaiting_dup":
        if text.lower() == "done":
            if not state["dups"]:
                await message.reply_text("❌ Koi duplicate nahi add kiya. /setup se dobara karein.", parse_mode=ParseMode.MARKDOWN)
                if uid in setup_states:
                    del setup_states[uid]
                return
            config["mappings"].append({
                "main_chat_id": state["main_id"],
                "main_chat_title": state["main_title"],
                "duplicates": state["dups"]
            })
            save_config(config)
            await message.reply_text("✅ **Setup Complete!** 🚀 Auto-forwarding started!", parse_mode=ParseMode.MARKDOWN)
            if uid in setup_states:
                del setup_states[uid]
            return

        try:
            if not text.startswith("-100"):
                await message.reply_text("❌ Sirf `-100` se shuru Chat ID daalein!", parse_mode=ParseMode.MARKDOWN)
                return
            chat = await client.get_chat(int(text))
            state["dups"].append({"chat_id": chat.id, "title": chat.title})
            await message.reply_text(
                f"✅ Added **{chat.title}**! (Total: {len(state['dups'])})\n\nSend another or type `done`.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ **Error:** {e}\n\nCheck: Bot Admin hai? @BotFather Privacy OFF?", parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("status"))
async def status_handler(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 **No mappings configured.**", parse_mode=ParseMode.MARKDOWN)
        return
    txt = "📋 **Current Mappings:**\n\n"
    for i, m in enumerate(config["mappings"], 1):
        txt += f"**{i}. Main:** {m['main_chat_title']}\n"
        txt += f"   → **Duplicates:** {len(m['duplicates'])}\n"
        for d in m["duplicates"]:
            txt += f"      • {d['title']}\n"
        txt += "\n"
    await message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command("delete"))
async def delete_handler(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 Nothing to delete.", parse_mode=ParseMode.MARKDOWN)
        return
    buttons = []
    for i, m in enumerate(config["mappings"], 1):
        buttons.append([InlineKeyboardButton(f"{i}. {m['main_chat_title']} ({len(m['duplicates'])} dupes)", callback_data=f"del_{i-1}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_c")])
    await message.reply_text("🗑 **Select mapping to delete:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^del_"))
async def delete_callback(client, cb: CallbackQuery):
    data = cb.data
    if data == "del_c":
        await cb.message.edit_text("❌ Cancelled.")
        await cb.answer()
        return
    idx = int(data.split("_")[1])
    config = load_config()
    if idx < len(config["mappings"]):
        removed = config["mappings"].pop(idx)
        save_config(config)
        await cb.message.edit_text(f"✅ **Deleted:** {removed['main_chat_title']}", parse_mode=ParseMode.MARKDOWN)
    await cb.answer()

@app.on_message(filters.channel)
async def auto_forward_handler(client, message: Message):
    config = load_config()
    cid = message.chat.id
    for m in config["mappings"]:
        if m["main_chat_id"] == cid:
            for d in m["duplicates"]:
                try:
                    await message.copy(chat_id=d["chat_id"])
                    logging.info(f"✅ Forwarded to {d['title']}")
                except Exception as e:
                    logging.error(f"❌ Failed to {d['title']}: {e}")
            break

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting bot...")
        app.run()
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped")
    except Exception as e:
        logging.exception(f"Fatal: {e}")
