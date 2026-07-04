import logging
from telegram import Update
from telegram.ext import (
CommandHandler,
CallbackQueryHandler,
MessageHandler,
filters,
ContextTypes,
Application
)
import config
import storage
import keyboards
import utils
logger = logging.getLogger(__name__)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
"""Handles the /start command and shows the main menu."""
user = update.effective_user
if not user:
return
storage.clear_state(user.id)
reply_markup = keyboards.get_main_menu_keyboard()
if update.message:
await update.message.reply_text(
text="Welcome to the Channel Forwarder Bot! Use the options below to manage your channel forwarding setup.",
reply_markup=reply_markup
)
elif update.callback_query:
await update.callback_query.message.edit_text(
text="Welcome to the Channel Forwarder Bot! Use the options below to manage your channel forwarding setup.",
reply_markup=reply_markup
)
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
"""Handles all inline keyboard callbacks."""
query = update.callback_query
if not query:
return
await query.answer()
user_id = query.from_user.id
data = query.data
if not data:
return
if data == "setup_main":
storage.update_state(user_id, config.STATE_AWAITING_MAIN_ID)
await query.message.edit_text(
text="Please send me the Chat ID of your Main Channel (e.g., -1001234567890):\nMake sure the bot is an admin in that channel first.",
reply_markup=keyboards.get_cancel_keyboard()
)
elif data == "setup_new":
storage.update_state(user_id, config.STATE_AWAITING_MAIN_ID)
await query.message.edit_text(
text="Please send me the Chat ID of the new Main Channel (e.g., -1001234567890):\nMake sure the bot is an admin in that channel first.",
reply_markup=keyboards.get_cancel_keyboard()
)
elif data == "my_channels":
mappings = storage.get_all_mappings(user_id)
if not mappings:
await query.message.edit_text(
text="You haven't configured any channels yet.",
reply_markup=keyboards.get_no_channels_keyboard()
)
else:
await query.message.edit_text(
text="Select a configured Main Channel to view details or manage:",
reply_markup=keyboards.get_channels_list_keyboard(mappings)
)
elif data == "finish_setup":
storage.clear_state(user_id)
reply_markup = keyboards.get_main_menu_keyboard()
await query.message.edit_text(
text="Setup completed successfully! Your channels are now configured.",
reply_markup=reply_markup
)
elif data == "cancel_setup":
storage.clear_state(user_id)
reply_markup = keyboards.get_main_menu_keyboard()
await query.message.edit_text(
text="Setup cancelled. Returned to the main menu.",
reply_markup=reply_markup
)
elif data == "back_home":
storage.clear_state(user_id)
reply_markup = keyboards.get_main_menu_keyboard()
await query.message.edit_text(
text="Welcome to the Channel Forwarder Bot! Use the options below to manage your channel forwarding setup.",
reply_markup=reply_markup
)
elif data.startswith("view_"):
chat_id = data.split("_")[1]
duplicates = storage.get_duplicates(user_id, chat_id)
await query.message.edit_text(
text=f"**Main Channel:** {chat_id}\n\n**Duplicate Channels:**\n" +
("\n".join([f"- {dup}" for dup in duplicates]) if duplicates else "None configured yet."),
reply_markup=keyboards.get_channel_management_keyboard(chat_id),
parse_mode="Markdown"
)
elif data.startswith("remove_"):
chat_id = data.split("_")[1]
storage.remove_main_channel(user_id, chat_id)
reply_markup = keyboards.get_main_menu_keyboard()
await query.message.edit_text(
text=f"Main channel {chat_id} and all its linked target channels have been removed.",
reply_markup=reply_markup
)
elif data.startswith("adddup_"):
chat_id = data.split("_")[1]
storage.set_current_main(user_id, chat_id)
storage.update_state(user_id, config.STATE_AWAITING_DUP_ID)
await query.message.edit_text(
text=f"Please send the Chat ID for a duplicate channel targeting Main Channel {chat_id}.\nSend 'done' when you are finished adding duplicate channels.",
reply_markup=keyboards.get_cancel_keyboard()
)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
"""Handles text messages and routing based on the user's state."""
user = update.effective_user
if not user or not update.message or not update.message.text:
return
user_id = user.id
text = update.message.text.strip()
user_data = storage.get_user(user_id)
state = user_data.get("state") if user_data else None
if state == config.STATE_AWAITING_MAIN_ID:
if not utils.validate_chat_id(text):
await update.message.reply_text(
text="Invalid Chat ID format. Please send a valid ID (e.g., -1001234567890):",
reply_markup=keyboards.get_cancel_keyboard()
)
return
if storage.channel_exists(user_id, text):
await update.message.reply_text(
text="This Main Channel is already configured. Please provide a different Chat ID:",
reply_markup=keyboards.get_cancel_keyboard()
)
return
is_admin = await utils.verify_bot_admin(context.application.bot, text)
if not is_admin:
await update.message.reply_text(
text="Verification failed. Please ensure the bot is added to that channel as an administrator with permission to post messages, then try again:",
reply_markup=keyboards.get_cancel_keyboard()
)
return
storage.add_main_channel(user_id, text)
storage.set_current_main(user_id, text)
storage.update_state(user_id, config.STATE_AWAITING_DUP_ID)
await update.message.reply_text(
text=f"Main Channel {text} configured successfully!\n\nNow, please send the Chat ID for a target/duplicate channel to forward posts to. Alternatively, send 'done' if you do not wish to add any now.",
reply_markup=keyboards.get_cancel_keyboard()
)
elif state == config.STATE_AWAITING_DUP_ID:
if text.lower() == "done":
storage.clear_state(user_id)
await update.message.reply_text(
text="Configuration update finished.",
reply_markup=keyboards.get_main_menu_keyboard()
)
return
if not utils.validate_chat_id(text):
await update.message.reply_text(
text="Invalid Chat ID format. Please send a valid ID (e.g., -1001234567890) or 'done' to finish:",
reply_markup=keyboards.get_cancel_keyboard()
)
return
current_main = storage.get_current_main(user_id)
if not current_main:
storage.clear_state(user_id)
await update.message.reply_text(
text="Session lost. Please restart the configuration process.",
reply_markup=keyboards.get_main_menu_keyboard()
)
return
if text == current_main:
await update.message.reply_text(
text="The target duplicate channel cannot be identical to the main channel. Please provide a different Chat ID:",
reply_markup=keyboards.get_cancel_keyboard()
)
return
if storage.duplicate_exists(user_id, current_main, text):
await update.message.reply_text(
text="This duplicate channel is already configured for this main channel. Please provide a different Chat ID:",
reply_markup=keyboards.get_cancel_keyboard()
)
return
is_admin = await utils.verify_bot_admin(context.application.bot, text)
if not is_admin:
await update.message.reply_text(
text="Verification failed. Please ensure the bot is added to that target channel as an administrator, then try again:",
reply_markup=keyboards.get_cancel_keyboard()
)
return
storage.add_duplicate_channel(user_id, current_main, text)
await update.message.reply_text(
text=f"Duplicate channel {text} successfully linked!\n\nYou can send another duplicate channel Chat ID, or send 'done' to finalize.",
reply_markup=keyboards.get_cancel_keyboard()
)
else:
await update.message.reply_text(
text="I did not understand that command or message. Please use the menu buttons below to interact with me.",
reply_markup=keyboards.get_main_menu_keyboard()
)
def register_handlers(application: Application) -> None:
"""Registers all application level handlers for the bot."""
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CallbackQueryHandler(handle_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
