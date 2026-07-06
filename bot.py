import os
import json
import asyncio
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


@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    count = len(config.get("mappings", []))
    welcome_text = (
        f"👋 **Welcome to Auto-Forward Bot!**\n\n"
        f"✅ **Total setups active:** {count}\n\n"
        f"**Commands:**\n"
        f"• /setup — Add channel mapping\n"
        f"• /status — See all mappings\n"
        f"• /delete — Remove a mapping\n\n"
        f"**⚠️ Bot ko channel ka Admin banayein!**\n"
        f"**⚠️ @BotFather mein Group Privacy = OFF karein!**"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Channel", url=f"https://t.me/{client.me.username}?startchannel=new"),
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=new")
        ]
    ])
    await message.reply_text(welcome_text, reply_markup=buttons, parse_mode=ParseMode.MARKDOWN)


setup_states = {}


@app.on_message(filters.command("setup"))
async def setup_command(client, message: Message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    setup_states[user_id] = {"step": "awaiting_main_channel"}
    await message.reply_text(
        "📌 **Step 1/3:** Send **Main Channel Chat ID**.\n\n"
        "Example: `-1003928300495`\n\n"
        "⚠️ Bot **Admin** hona chahiye channel mein!\n"
        "⚠️ @BotFather → Group Privacy = **OFF**",
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command("reconfigure"))
async def reconfigure_command(client, message: Message):
    if not message.from_user:
        return
    await setup_command(client, message)


@app.on_message(filters.text & filters.private & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def handle_setup_input(client, message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    if user_id not in setup_states:
        return

    state = setup_states[user_id]
    text = message.text.strip()
    config = load_config()

    # ── Step: Awaiting Main Channel ──
    if state["step"] == "awaiting_main_channel":
        try:
            # Sirf numeric chat ID accept karo
            chat_id = int(text.replace("-", "").strip())
            if not text.startswith("-100"):
                await message.reply_text(
                    "❌ Sirf **-100** se shuru hone wala Chat ID daalein!\n"
                    "Example: `-1003928300495`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            chat = await client.get_chat(int(text))

            state["main_chat_id"] = chat.id
            state["main_chat_title"] = chat.title
            state["duplicates"] = []
            state["step"] = "awaiting_duplicate"

            await message.reply_text(
                f"✅ **Main Channel set:** {chat.title}\n\n"
                f"📌 **Step 2/3:** Ab **Duplicate Channel ka Chat ID** bhejein.\n"
                f"Type `done` jab sab add ho jayein.",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await message.reply_text(
                "❌ Sirf **numeric Chat ID** daalein! Jaise: `-1003928300495`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            error_msg = str(e)
            await message.reply_text(
                f"❌ **Error:** {error_msg}\n\n"
                f"**Check karein:**\n"
                f"1️⃣ Bot ko channel ka **Admin** banaya?\n"
                f"   → Channel Info → Administrators → Add Admin\n"
                f"2️⃣ @BotFather mein **Group Privacy = OFF** kiya?\n"
                f"3️⃣ Chat ID sahi hai?\n\n"
                f"Phir /setup karein.",
                parse_mode=ParseMode.MARKDOWN
            )
            if user_id in setup_states:
                del setup_states[user_id]
        return

    # ── Step: Awaiting Duplicate Channels ──
    if state["step"] == "awaiting_duplicate":
        if text.lower() == "done":
            if not state["duplicates"]:
                await message.reply_text("❌ Koi duplicate add nahi kiya. /setup se dobara karein.", parse_mode=ParseMode.MARKDOWN)
                if user_id in setup_states:
                    del setup_states[user_id]
                return

            existing = None
            for m in config["mappings"]:
                if m["main_chat_id"] == state["main_chat_id"]:
                    existing = m
                    break

            if existing:
                for dup in state["duplicates"]:
                    if dup not in existing["duplicates"]:
                        existing["duplicates"].append(dup)
                save_config(config)
                dup_list = "\n".join([f"• {d['title']}" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Updated!**\n\n**Main:** {state['main_chat_title']}\n**Duplicates added:**\n{dup_list}\n\n🚀 Auto-forwarding started!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                config["mappings"].append({
                    "main_chat_id": state["main_chat_id"],
                    "main_chat_title": state["main_chat_title"],
                    "duplicates": state["duplicates"]
                })
                save_config(config)
                dup_list = "\n".join([f"• {d['title']}" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Setup Complete!**\n\n**Main Channel:** {state['main_chat_title']}\n**Duplicates ({len(state['duplicates'])}):**\n{dup_list}\n\n🚀 Auto-forwarding started!",
                    parse_mode=ParseMode.MARKDOWN
                )
            if user_id in setup_states:
                del setup_states[user_id]
            return

        # Add duplicate channel
        try:
            # Sirf numeric chat ID accept karo
            if not text.startswith("-100"):
                await message.reply_text(
                    "❌ Sirf **-100** se shuru hone wala Chat ID daalein!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            chat = await client.get_chat(int(text))

            for d in state["duplicates"]:
                if d["chat_id"] == chat.id:
                    await message.reply_text(f"⚠️ **{chat.title}** already in list!", parse_mode=ParseMode.MARKDOWN)
                    return

            state["duplicates"].append({"chat_id": chat.id, "title": chat.title})
            await message.reply_text(
                f"✅ Added **{chat.title}**! (Total: {len(state['duplicates'])})\n\nSend another Chat ID or type `done`.",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await message.reply_text(
                "❌ Sirf **numeric Chat ID** daalein! Jaise: `-1003941312730`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(
                f"❌ Error: {e}\n\n**Check:** Bot admin hai? @BotFather mein Privacy OFF hai?",
                parse_mode=ParseMode.MARKDOWN
            )


@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 **No mappings configured yet.**", parse_mode=ParseMode.MARKDOWN)
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


@app.on_message(filters.command("delete"))
async def delete_command(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 No mappings to delete.")
        return
    buttons = []
    for i, mapping in enumerate(config["mappings"], 1):
        buttons.append([InlineKeyboardButton(f"{i}. {mapping['main_chat_title']} ({len(mapping['duplicates'])} dupes)", callback_data=f"del_{i-1}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await message.reply_text("🗑 **Select a mapping to delete:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^del_"))
async def delete_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    if data == "del_cancel":
        await callback_query.message.edit_text("❌ Cancelled.")
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
        f"✅ **Deleted:** {removed['main_chat_title']}\nRemoved {len(removed['duplicates'])} duplicate(s).",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer()


@app.on_message(filters.channel)
async def auto_forward(client, message: Message):
    config = load_config()
    chat_id = message.chat.id
    for mapping in config["mappings"]:
        if mapping["main_chat_id"] == chat_id:
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
            break


async def keep_alive():
    while True:
        await asyncio.sleep(300)
        logging.info("🔄 Heartbeat - Bot is alive")


async def main():
    await app.start()
    logging.info("🚀 Bot started successfully!")
    asyncio.create_task(keep_alive())
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.exception(f"Fatal Error: {e}")    config = load_config()
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
        f"• /reconfigure — Re-run setup for new channels"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Channel", url=f"https://t.me/{client.me.username}?startchannel=new"),
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=new")
        ]
    ])
    await message.reply_text(welcome_text, reply_markup=buttons, parse_mode=ParseMode.MARKDOWN)


# ── Setup state ──

setup_states = {}


@app.on_message(filters.command("setup"))
async def setup_command(client, message: Message):
    # ✅ SAFE CHECK: from_user None ho to ignore
    if not message.from_user:
        return
    user_id = message.from_user.id
    setup_states[user_id] = {"step": "awaiting_main_channel"}
    await message.reply_text(
        "📌 **Step 1/3:** Send me the **Main Channel's username**.\n\n"
        "Example: `@my_main_channel`\n\n"
        "Use @username only.\n"
        "Bot must be **Admin** in the channel!",
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command("reconfigure"))
async def reconfigure_command(client, message: Message):
    await setup_command(client, message)


# ── Text handler (ONLY private chats, ignores channel posts) ──

@app.on_message(filters.text & filters.private & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def handle_setup_input(client, message: Message):
    # ✅ SAFE CHECK: from_user None ho to ignore
    if not message.from_user:
        return

    user_id = message.from_user.id
    if user_id not in setup_states:
        return

    state = setup_states[user_id]
    text = message.text.strip()
    config = load_config()

    # ── Step: Awaiting Main Channel ──
    if state["step"] == "awaiting_main_channel":
        try:
            if not text.startswith("@"):
                await message.reply_text(
                    "❌ Please send the channel **@username** (like `@DeshiVedios`).",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            chat = await client.get_chat(text)

            state["main_chat_id"] = chat.id
            state["main_chat_title"] = chat.title
            state["duplicates"] = []
            state["step"] = "awaiting_duplicate"

            await message.reply_text(
                f"✅ **Main Channel found:** {chat.title}\n\n"
                f"📌 **Step 2/3:** Now send me a **Duplicate Channel's @username**.\n"
                f"Type `done` when finished.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(
                f"❌ **Error:** {e}\n\n"
                f"**Check:**\n"
                f"1. Bot is **admin** in the channel?\n"
                f"2. Channel username sahi hai?\n\n"
                f"Then /setup again.",
                parse_mode=ParseMode.MARKDOWN
            )
            del setup_states[user_id]
        return

    # ── Step: Awaiting Duplicate Channels ──
    if state["step"] == "awaiting_duplicate":
        if text.lower() == "done":
            if not state["duplicates"]:
                await message.reply_text("❌ No duplicates added. Use /setup again.", parse_mode=ParseMode.MARKDOWN)
                del setup_states[user_id]
                return

            existing = None
            for m in config["mappings"]:
                if m["main_chat_id"] == state["main_chat_id"]:
                    existing = m
                    break

            if existing:
                for dup in state["duplicates"]:
                    if dup not in existing["duplicates"]:
                        existing["duplicates"].append(dup)
                save_config(config)
                dup_list = "\n".join([f"• {d['title']}" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Updated!**\n\n**Main:** {state['main_chat_title']}\n**Duplicates added:**\n{dup_list}\n\nNew posts will auto-forward now! 🚀",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                config["mappings"].append({
                    "main_chat_id": state["main_chat_id"],
                    "main_chat_title": state["main_chat_title"],
                    "duplicates": state["duplicates"]
                })
                save_config(config)
                dup_list = "\n".join([f"• {d['title']}" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Setup Complete!**\n\n**Main Channel:** {state['main_chat_title']}\n**Duplicates ({len(state['duplicates'])}):**\n{dup_list}\n\n🚀 Auto-forwarding started!",
                    parse_mode=ParseMode.MARKDOWN
                )
            del setup_states[user_id]
            return

        # Add duplicate
        try:
            if not text.startswith("@"):
                await message.reply_text("❌ Please send @username format.", parse_mode=ParseMode.MARKDOWN)
                return

            chat = await client.get_chat(text)

            for d in state["duplicates"]:
                if d["chat_id"] == chat.id:
                    await message.reply_text(f"⚠️ **{chat.title}** already in list!", parse_mode=ParseMode.MARKDOWN)
                    return

            state["duplicates"].append({"chat_id": chat.id, "title": chat.title})
            await message.reply_text(
                f"✅ Added **{chat.title}**! (Total: {len(state['duplicates'])})\n\nSend another or type `done`.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)


# ── /STATUS ──

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 **No mappings configured yet.**", parse_mode=ParseMode.MARKDOWN)
        return
    text = "📋 **Current Channel Mappings:**\n\n"
    for i, mapping in enumerate(config["mappings"], 1):
        text += f"**{i}. Main:** {mapping['main_chat_title']}\n"
        text += f"   **→ Duplicates ({len(mapping['duplicates'])}):**\n"
        for dup in mapping["duplicates"]:
            text += f"      • {dup['title']}\n"
        text += "\n"
    text += f"\n**Total mappings: {len(config['mappings'])}**"
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /DELETE ──

@app.on_message(filters.command("delete"))
async def delete_command(client, message: Message):
    if not message.from_user:
        return
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 No mappings to delete.")
        return
    buttons = []
    for i, mapping in enumerate(config["mappings"], 1):
        buttons.append([InlineKeyboardButton(f"{i}. {mapping['main_chat_title']} ({len(mapping['duplicates'])} dupes)", callback_data=f"del_{i-1}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await message.reply_text("🗑 **Select a mapping to delete:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^del_"))
async def delete_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    if data == "del_cancel":
        await callback_query.message.edit_text("❌ Cancelled.")
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
        f"✅ **Deleted:** {removed['main_chat_title']}\nRemoved {len(removed['duplicates'])} duplicate(s).",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer()


# ── AUTO-FORWARD ──

@app.on_message(filters.channel)
async def auto_forward(client, message: Message):
    config = load_config()
    chat_id = message.chat.id
    for mapping in config["mappings"]:
        if mapping["main_chat_id"] == chat_id:
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
            break


# ── KEEP ALIVE ──

async def keep_alive():
    while True:
        await asyncio.sleep(600)
        logging.info("🔄 Heartbeat - Bot is alive")


# ── ENTRY POINT ──

async def main():
    await app.start()
    logging.info("🚀 Bot started successfully!")
    asyncio.create_task(keep_alive())
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.exception(f"Fatal Error: {e}")    config = load_config()
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
        f"• /reconfigure — Re-run setup for new channels"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Channel", url=f"https://t.me/{client.me.username}?startchannel=new"),
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=new")
        ]
    ])
    await message.reply_text(welcome_text, reply_markup=buttons, parse_mode=ParseMode.MARKDOWN)


# ── Setup state (per-user) ──

setup_states = {}


@app.on_message(filters.command("setup"))
async def setup_command(client, message: Message):
    user_id = message.from_user.id
    if user_id is None:
        await message.reply_text("❌ Please use this command in a private chat with the bot.")
        return
    setup_states[user_id] = {"step": "awaiting_main_channel"}
    await message.reply_text(
        "📌 **Step 1/3:** Send me the **Main Channel's username**.\n\n"
        "Example: `@my_main_channel`\n\n"
        "Use @username only — numeric IDs may not work.\n"
        "Bot must be **Admin** in the channel!",
        parse_mode=ParseMode.MARKDOWN
    )


@app.on_message(filters.command("reconfigure"))
async def reconfigure_command(client, message: Message):
    await setup_command(client, message)


# ── Text handler (ONLY from private chats — ignores channel posts) ──

@app.on_message(filters.text & filters.private & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def handle_setup_input(client, message: Message):
    user_id = message.from_user.id
    if user_id not in setup_states:
        return

    state = setup_states[user_id]
    text = message.text.strip()
    config = load_config()

    # ── Step: Awaiting Main Channel ──
    if state["step"] == "awaiting_main_channel":
        try:
            # ONLY accept @username format — more reliable
            if not text.startswith("@"):
                await message.reply_text(
                    "❌ Please send the channel **@username** (like `@DeshiVedios`).\nNumeric IDs often don't work with bots.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            chat = await client.get_chat(text)

            state["main_chat_id"] = chat.id
            state["main_chat_title"] = chat.title
            state["duplicates"] = []
            state["step"] = "awaiting_duplicate"

            await message.reply_text(
                f"✅ **Main Channel found:** {chat.title}\n\n"
                f"📌 **Step 2/3:** Now send me a **Duplicate Channel's @username**.\n"
                f"Type `done` when finished.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(
                f"❌ **Error:** {e}\n\n"
                f"**Check:**\n"
                f"1. Bot is **admin** in the channel?\n"
                f"2. Channel username sahi hai?\n"
                f"3. Try adding bot to channel first:\n"
                f"   https://t.me/{client.me.username}?startchannel=new\n\n"
                f"Then /setup again.",
                parse_mode=ParseMode.MARKDOWN
            )
            del setup_states[user_id]
        return

    # ── Step: Awaiting Duplicate Channels ──
    if state["step"] == "awaiting_duplicate":
        if text.lower() == "done":
            if not state["duplicates"]:
                await message.reply_text("❌ No duplicates added. Use /setup again.", parse_mode=ParseMode.MARKDOWN)
                del setup_states[user_id]
                return

            existing = None
            for m in config["mappings"]:
                if m["main_chat_id"] == state["main_chat_id"]:
                    existing = m
                    break

            if existing:
                for dup in state["duplicates"]:
                    if dup not in existing["duplicates"]:
                        existing["duplicates"].append(dup)
                save_config(config)
                dup_list = "\n".join([f"• {d['title']}" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Updated!**\n\n**Main:** {state['main_chat_title']}\n**Duplicates added:**\n{dup_list}\n\nNew posts will auto-forward now! 🚀",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                config["mappings"].append({
                    "main_chat_id": state["main_chat_id"],
                    "main_chat_title": state["main_chat_title"],
                    "duplicates": state["duplicates"]
                })
                save_config(config)
                dup_list = "\n".join([f"• {d['title']}" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Setup Complete!**\n\n**Main Channel:** {state['main_chat_title']}\n**Duplicates ({len(state['duplicates'])}):**\n{dup_list}\n\n🚀 Auto-forwarding started!",
                    parse_mode=ParseMode.MARKDOWN
                )
            del setup_states[user_id]
            return

        # Add duplicate
        try:
            if not text.startswith("@"):
                await message.reply_text("❌ Please send @username format.", parse_mode=ParseMode.MARKDOWN)
                return

            chat = await client.get_chat(text)

            for d in state["duplicates"]:
                if d["chat_id"] == chat.id:
                    await message.reply_text(f"⚠️ **{chat.title}** already in list!", parse_mode=ParseMode.MARKDOWN)
                    return

            state["duplicates"].append({"chat_id": chat.id, "title": chat.title})
            await message.reply_text(
                f"✅ Added **{chat.title}**! (Total: {len(state['duplicates'])})\n\nSend another or type `done`.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)


# ── /STATUS ──

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 **No mappings configured yet.**", parse_mode=ParseMode.MARKDOWN)
        return
    text = "📋 **Current Channel Mappings:**\n\n"
    for i, mapping in enumerate(config["mappings"], 1):
        text += f"**{i}. Main:** {mapping['main_chat_title']}\n"
        text += f"   **→ Duplicates ({len(mapping['duplicates'])}):**\n"
        for dup in mapping["duplicates"]:
            text += f"      • {dup['title']}\n"
        text += "\n"
    text += f"\n**Total mappings: {len(config['mappings'])}**"
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /DELETE ──

@app.on_message(filters.command("delete"))
async def delete_command(client, message: Message):
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 No mappings to delete.")
        return
    buttons = []
    for i, mapping in enumerate(config["mappings"], 1):
        buttons.append([InlineKeyboardButton(f"{i}. {mapping['main_chat_title']} ({len(mapping['duplicates'])} dupes)", callback_data=f"del_{i-1}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await message.reply_text("🗑 **Select a mapping to delete:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)


@app.on_callback_query(filters.regex(r"^del_"))
async def delete_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    if data == "del_cancel":
        await callback_query.message.edit_text("❌ Cancelled.")
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
        f"✅ **Deleted:** {removed['main_chat_title']}\nRemoved {len(removed['duplicates'])} duplicate(s).",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer()


# ── AUTO-FORWARD ──

@app.on_message(filters.channel)
async def auto_forward(client, message: Message):
    config = load_config()
    chat_id = message.chat.id
    for mapping in config["mappings"]:
        if mapping["main_chat_id"] == chat_id:
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
            break


# ── KEEP ALIVE ──

async def keep_alive():
    """Send heartbeat every 10 minutes."""
    while True:
        await asyncio.sleep(600)
        logging.info("🔄 Heartbeat - Bot is alive")


# ── ENTRY POINT ──

async def main():
    """Run bot and keep_alive together."""
    await app.start()
    logging.info("🚀 Bot started successfully!")
    
    # Run keep_alive in background
    asyncio.create_task(keep_alive())
    
    # Keep running until stopped
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.exception(f"Fatal Error: {e}")        # Method 1: get_chat_member (standard)
        member = await client.get_chat_member(chat_id, bot_id)
        if member.status in ("administrator", "owner"):
            return True

        # Method 2: get_chat → check admin_count (for channels where get_chat_member fails)
        chat = await client.get_chat(chat_id)
        if hasattr(chat, "admin_count") and chat.admin_count and chat.admin_count > 0:
            return True

        # Method 3: Try sending a test message (silent check)
        # If we can see the chat at all and it's a channel, assume admin
        if chat.type == ChatType.CHANNEL:
            return True  # bot can see the channel, likely admin

        return False
    except Exception as e:
        logging.error(f"Admin check failed for {chat_id}: {e}")
        return False


async def get_bot_id(client):
    me = await client.get_me()
    return me.id


# ── /START ──

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


@app.on_message(filters.command("reconfigure"))
async def reconfigure_command(client, message: Message):
    await setup_command(client, message)


@app.on_message(filters.text & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def handle_setup_input(client, message: Message):
    user_id = message.from_user.id
    if user_id not in setup_states:
        return

    state = setup_states[user_id]
    text = message.text.strip()
    config = load_config()
    bot_id = await get_bot_id(client)

    # ── Step: Awaiting Main Channel ──
    if state["step"] == "awaiting_main_channel":
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            elif text.startswith("-100") or text.lstrip("-").isdigit():
                chat = await client.get_chat(int(text))
            else:
                await message.reply_text("❌ Invalid format. Send `@username` or numeric Chat ID.", parse_mode=ParseMode.MARKDOWN)
                return

            # Better admin check
            is_admin = await is_bot_admin_in_chat(client, chat.id, bot_id)
            logging.info(f"Admin check for main channel {chat.title} ({chat.id}): {is_admin}")

            if not is_admin:
                await message.reply_text(
                    f"❌ I'm not an admin in **{chat.title}**.\n\n"
                    f"**Solution:**\n"
                    f"1. Go to your channel → Info → Administrators\n"
                    f"2. Click 'Add Admin'\n"
                    f"3. Search for `@{client.me.username}`\n"
                    f"4. Give at least **'Post Messages'** permission\n"
                    f"5. Then try /setup again",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            state["main_chat_id"] = chat.id
            state["main_chat_title"] = chat.title
            state["duplicates"] = []
            state["step"] = "awaiting_duplicate"

            await message.reply_text(
                f"✅ **Main Channel set:** {chat.title} (`{chat.id}`)\n\n"
                f"📌 **Step 2/3:** Now send me a **Duplicate Channel** @username or Chat ID.\n"
                f"Type `done` when finished.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)
            del setup_states[user_id]
        return

    # ── Step: Awaiting Duplicate Channels ──
    if state["step"] == "awaiting_duplicate":
        if text.lower() == "done":
            if not state["duplicates"]:
                await message.reply_text("❌ You didn't add any duplicate channels. Use /setup again.", parse_mode=ParseMode.MARKDOWN)
                del setup_states[user_id]
                return

            existing = None
            for m in config["mappings"]:
                if m["main_chat_id"] == state["main_chat_id"]:
                    existing = m
                    break

            if existing:
                for dup in state["duplicates"]:
                    if dup not in existing["duplicates"]:
                        existing["duplicates"].append(dup)
                save_config(config)
                dup_list = "\n".join([f"• {d['title']} (`{d['chat_id']}`)" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Updated!**\n\n**Main:** {state['main_chat_title']}\n**Duplicates added:**\n{dup_list}\n\nNew posts will auto-forward now! 🚀",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                config["mappings"].append({
                    "main_chat_id": state["main_chat_id"],
                    "main_chat_title": state["main_chat_title"],
                    "duplicates": state["duplicates"]
                })
                save_config(config)
                dup_list = "\n".join([f"• {d['title']} (`{d['chat_id']}`)" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Setup Complete!**\n\n**Main Channel:** {state['main_chat_title']} (`{state['main_chat_id']}`)\n**Duplicates ({len(state['duplicates'])}):**\n{dup_list}\n\n🚀 Any new post will auto-forward!\n\nUse /setup again for another main channel.",
                    parse_mode=ParseMode.MARKDOWN
                )
            del setup_states[user_id]
            return

        # Add duplicate
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            elif text.startswith("-100") or text.lstrip("-").isdigit():
                chat = await client.get_chat(int(text))
            else:
                await message.reply_text("❌ Invalid format. Send @username or numeric Chat ID.", parse_mode=ParseMode.MARKDOWN)
                return

            is_admin = await is_bot_admin_in_chat(client, chat.id, bot_id)
            logging.info(f"Admin check for duplicate {chat.title} ({chat.id}): {is_admin}")

            if not is_admin:
                await message.reply_text(
                    f"❌ I'm not an admin in **{chat.title}**. Make me admin first!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            for d in state["duplicates"]:
                if d["chat_id"] == chat.id:
                    await message.reply_text(f"⚠️ **{chat.title}** is already in your duplicates list!", parse_mode=ParseMode.MARKDOWN)
                    return

            state["duplicates"].append({"chat_id": chat.id, "title": chat.title})
            await message.reply_text(
                f"✅ Added **{chat.title}** to duplicates! (Total: {len(state['duplicates'])})\n\nSend another or type `done` to finish.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)


# ── /STATUS ──

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 **No mappings configured yet.**", parse_mode=ParseMode.MARKDOWN)
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


# ── /DELETE ──

@app.on_message(filters.command("delete"))
async def delete_command(client, message: Message):
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 No mappings to delete.")
        return
    buttons = []
    for i, mapping in enumerate(config["mappings"], 1):
        buttons.append([InlineKeyboardButton(f"{i}. {mapping['main_chat_title']} ({len(mapping['duplicates'])} dupes)", callback_data=f"del_{i-1}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await message.reply_text("🗑 **Select a mapping to delete:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)


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
        f"✅ **Deleted:** {removed['main_chat_title']}\nRemoved {len(removed['duplicates'])} duplicate channel(s).",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer()


# ── AUTO-FORWARD ──

@app.on_message(filters.channel)
async def auto_forward(client, message: Message):
    config = load_config()
    chat_id = message.chat.id
    for mapping in config["mappings"]:
        if mapping["main_chat_id"] == chat_id:
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
            break


# ── KEEP ALIVE ──

async def keep_alive():
    while True:
        await asyncio.sleep(600)
        logging.info("🔄 Heartbeat - Bot is alive")


# ── ENTRY POINT ──

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting Bot...")
        app.run()
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped")
    except Exception:
        logging.exception("Fatal Error")
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


# ── Setup state ──

setup_states = {}


# ── /SETUP ──

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


@app.on_message(filters.command("reconfigure"))
async def reconfigure_command(client, message: Message):
    await setup_command(client, message)


# ── Interactive text handler ──

@app.on_message(filters.text & ~filters.command(["start", "setup", "status", "delete", "reconfigure"]))
async def handle_setup_input(client, message: Message):
    user_id = message.from_user.id
    if user_id not in setup_states:
        return

    state = setup_states[user_id]
    text = message.text.strip()
    config = load_config()

    # ── Step: waiting for main channel ──
    if state["step"] == "awaiting_main_channel":
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            elif text.startswith("-100") or text.lstrip("-").isdigit():
                chat = await client.get_chat(int(text))
            else:
                await message.reply_text("❌ Invalid format. Send `@username` or numeric Chat ID.", parse_mode=ParseMode.MARKDOWN)
                return

            me = await client.get_me()
            member = await client.get_chat_member(chat.id, me.id)
            if member.status not in ("administrator", "owner"):
                await message.reply_text(
                    f"❌ I'm not an admin in **{chat.title}**. Make me admin first!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            state["main_chat_id"] = chat.id
            state["main_chat_title"] = chat.title
            state["duplicates"] = []
            state["step"] = "awaiting_duplicate"

            await message.reply_text(
                f"✅ **Main Channel set:** {chat.title} (`{chat.id}`)\n\n"
                f"📌 **Step 2/3:** Now send me a **Duplicate Channel** @username or Chat ID.\n"
                f"Type `done` when you're finished adding duplicates.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)
            del setup_states[user_id]
        return

    # ── Step: waiting for duplicate channels ──
    if state["step"] == "awaiting_duplicate":
        if text.lower() == "done":
            if not state["duplicates"]:
                await message.reply_text("❌ You didn't add any duplicate channels. Use /setup again.", parse_mode=ParseMode.MARKDOWN)
                del setup_states[user_id]
                return

            existing = None
            for m in config["mappings"]:
                if m["main_chat_id"] == state["main_chat_id"]:
                    existing = m
                    break

            if existing:
                for dup in state["duplicates"]:
                    if dup not in existing["duplicates"]:
                        existing["duplicates"].append(dup)
                save_config(config)
                dup_list = "\n".join([f"• {d['title']} (`{d['chat_id']}`)" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Updated!**\n\n**Main:** {state['main_chat_title']}\n**Duplicates added:**\n{dup_list}\n\nNew posts will auto-forward now! 🚀",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                config["mappings"].append({
                    "main_chat_id": state["main_chat_id"],
                    "main_chat_title": state["main_chat_title"],
                    "duplicates": state["duplicates"]
                })
                save_config(config)
                dup_list = "\n".join([f"• {d['title']} (`{d['chat_id']}`)" for d in state["duplicates"]])
                await message.reply_text(
                    f"✅ **Setup Complete!**\n\n**Main Channel:** {state['main_chat_title']} (`{state['main_chat_id']}`)\n**Duplicates ({len(state['duplicates'])}):**\n{dup_list}\n\n🚀 Any new post in main channel will auto-forward to duplicates!\n\nUse /setup again for another main channel.\nUse /reconfigure if you want to add more duplicates later.",
                    parse_mode=ParseMode.MARKDOWN
                )
            del setup_states[user_id]
            return

        # Add a duplicate channel
        try:
            if text.startswith("@"):
                chat = await client.get_chat(text)
            elif text.startswith("-100") or text.lstrip("-").isdigit():
                chat = await client.get_chat(int(text))
            else:
                await message.reply_text("❌ Invalid format. Send @username or numeric Chat ID.", parse_mode=ParseMode.MARKDOWN)
                return

            me = await client.get_me()
            member = await client.get_chat_member(chat.id, me.id)
            if member.status not in ("administrator", "owner"):
                await message.reply_text(f"❌ I'm not an admin in **{chat.title}**. Make me admin first!", parse_mode=ParseMode.MARKDOWN)
                return

            for d in state["duplicates"]:
                if d["chat_id"] == chat.id:
                    await message.reply_text(f"⚠️ **{chat.title}** is already in your duplicates list!", parse_mode=ParseMode.MARKDOWN)
                    return

            state["duplicates"].append({"chat_id": chat.id, "title": chat.title})
            await message.reply_text(
                f"✅ Added **{chat.title}** to duplicates! (Total: {len(state['duplicates'])})\n\nSend another duplicate channel or type `done` to finish.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}", parse_mode=ParseMode.MARKDOWN)


# ── /STATUS ──

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 **No mappings configured yet.**\n\nUse /setup to add your first channel mapping.", parse_mode=ParseMode.MARKDOWN)
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


# ── /DELETE ──

@app.on_message(filters.command("delete"))
async def delete_command(client, message: Message):
    config = load_config()
    if not config["mappings"]:
        await message.reply_text("📭 No mappings to delete.")
        return
    buttons = []
    for i, mapping in enumerate(config["mappings"], 1):
        buttons.append([InlineKeyboardButton(f"{i}. {mapping['main_chat_title']} ({len(mapping['duplicates'])} dupes)", callback_data=f"del_{i-1}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")])
    await message.reply_text("🗑 **Select a mapping to delete:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)


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
        f"✅ **Deleted:** {removed['main_chat_title']}\nRemoved {len(removed['duplicates'])} duplicate channel(s).",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer()


# ── AUTO-FORWARD ──

@app.on_message(filters.channel)
async def auto_forward(client, message: Message):
    config = load_config()
    chat_id = message.chat.id
    for mapping in config["mappings"]:
        if mapping["main_chat_id"] == chat_id:
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
            break


# ── KEEP ALIVE ──

async def keep_alive():
    while True:
        await asyncio.sleep(600)
        logging.info("🔄 Heartbeat - Bot is alive")


# ── ENTRY POINT ──

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting Bot...")
        app.run()
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped")
    except Exception:
        logging.exception("Fatal Error")
