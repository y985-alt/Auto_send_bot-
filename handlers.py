"""
handlers.py

All Telegram-facing handlers for the bot:
    - /start and /id commands.
    - Three owner-only ConversationHandlers: Setup New Channel (source ->
      destination mapping wizard), Delete Source, Remove Destination.
    - A catch-all CallbackQueryHandler ("main menu router") for every
      non-conversation button: info screens, My Sources, My Destinations,
      Statistics, and their pagination.
    - A channel-post listener that triggers forwarder.process_new_post()
      whenever a registered source channel receives a new post.
    - A global error handler.

register_handlers(application) is the single function bot.py calls to wire
everything up, in an order where owner-only ConversationHandlers are checked
before the generic fallback router (see PTB handler-group precedence notes
inline below).
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from telegram import (
    Chat,
    InlineKeyboardMarkup,
    MessageOriginChannel,
    Update,
)
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings
from database import get_session
from forwarder import process_new_post
from keyboards import (
    build_back_to_main_keyboard,
    build_cancel_keyboard,
    build_confirm_keyboard,
    build_delete_source_keyboard,
    build_destination_selection_keyboard,
    build_main_menu_keyboard,
    build_my_destinations_keyboard,
    build_my_sources_keyboard,
    build_remove_destination_keyboard,
    build_source_selection_keyboard,
    build_statistics_keyboard,
    PAGE_SIZE,
)
from models import ChannelMapping, DestinationChannel, ForwardLog, SourceChannel
from states import CallbackData, ConversationState, UserDataKey
from utils import chunk_list, format_chat_label, is_owner, log_action, parse_chat_id, resolve_chat

logger = logging.getLogger("bot.handlers")

END = ConversationHandler.END

WELCOME_TEXT = (
    "👋 <b>Welcome to the Channel Forwarder Bot</b>\n\n"
    "I automatically copy every new post from your Source Channels to all "
    "the Destination Channels/Groups you map them to.\n\n"
    "Use the menu below to get started."
)

UNAUTHORIZED_TEXT = "🚫 This bot is privately owned and not available for public use."

# Local (non-shared) view-mode markers, used only inside this module to
# remember which read-only paginated list is currently on screen.
_VIEW_SOURCES = "sources"
_VIEW_DESTINATIONS = "destinations"
_CURRENT_VIEW_KEY = "current_readonly_view"


# ==========================================================================
# Shared helpers
# ==========================================================================


async def _reject_if_not_owner(update: Update) -> bool:
    """
    Answer/reply with an unauthorized notice if the sender is not the owner.

    Args:
        update: The incoming Update.

    Returns:
        True if the sender was rejected (caller should stop processing),
        False if the sender is the authorized owner.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if is_owner(user_id):
        return False

    if update.callback_query:
        await update.callback_query.answer(UNAUTHORIZED_TEXT, show_alert=True)
    elif update.message:
        await update.message.reply_text(UNAUTHORIZED_TEXT)
    return True


async def _validate_bot_is_admin(bot, chat: Chat) -> bool:
    """
    Check whether the bot has sufficient rights in a chat to send/read posts.

    Channels require the bot to be an administrator (Telegram only delivers
    channel_post updates to admin bots). Groups only require membership.

    Args:
        bot: The active Bot instance.
        chat: The Chat to validate.

    Returns:
        True if the bot's role in the chat is sufficient, False otherwise.
    """
    try:
        member = await bot.get_chat_member(chat.id, bot.id)
    except TelegramError:
        logger.exception("Failed to check bot membership in chat_id=%s", chat.id)
        return False

    if chat.type == ChatType.CHANNEL:
        return member.status in ("administrator", "creator")
    return member.status in ("administrator", "creator", "member")


def _extract_forwarded_chat(update: Update) -> tuple[int, str] | None:
    """
    Extract the origin chat ID/title from a forwarded channel message, if any.

    Args:
        update: The incoming Update containing a message.

    Returns:
        A (chat_id, title) tuple if the message was forwarded from a channel,
        else None.
    """
    message = update.message
    if message is None:
        return None
    origin = getattr(message, "forward_origin", None)
    if origin is not None and isinstance(origin, MessageOriginChannel):
        return origin.chat.id, origin.chat.title or "Untitled Channel"
    return None


async def _resolve_target_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Chat | None:
    """
    Resolve the chat a user is registering, from either a forwarded message
    or a typed chat ID / @username.

    Args:
        update: The incoming Update.
        context: The PTB context, used to access the Bot instance.

    Returns:
        The resolved Chat, or None if it could not be determined/validated.
    """
    forwarded = _extract_forwarded_chat(update)
    if forwarded is not None:
        chat_id, _title = forwarded
        try:
            return await context.bot.get_chat(chat_id)
        except TelegramError:
            logger.exception("Failed to fetch forwarded chat_id=%s", chat_id)
            return None

    if update.message and update.message.text:
        return await resolve_chat(context.bot, update.message.text)

    return None


async def _get_or_create_source(session, chat_id: int, title: str) -> SourceChannel:
    """Fetch an existing SourceChannel by chat_id, or create a new one."""
    stmt = select(SourceChannel).where(SourceChannel.chat_id == chat_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.title = title
        existing.is_active = True
        return existing

    source = SourceChannel(chat_id=chat_id, title=title, owner_id=settings.owner_id)
    session.add(source)
    await session.flush()
    return source


async def _get_or_create_destination(session, chat_id: int, title: str) -> DestinationChannel:
    """Fetch an existing DestinationChannel by chat_id, or create a new one."""
    stmt = select(DestinationChannel).where(DestinationChannel.chat_id == chat_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.title = title
        existing.is_active = True
        return existing

    destination = DestinationChannel(chat_id=chat_id, title=title, owner_id=settings.owner_id)
    session.add(destination)
    await session.flush()
    return destination


async def _get_or_create_mapping(session, source_id: int, destination_id: int) -> tuple[ChannelMapping, bool]:
    """Fetch an existing ChannelMapping, or create a new one. Returns (mapping, created)."""
    stmt = select(ChannelMapping).where(
        ChannelMapping.source_id == source_id, ChannelMapping.destination_id == destination_id
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        was_inactive = not existing.is_active
        existing.is_active = True
        return existing, was_inactive

    mapping = ChannelMapping(source_id=source_id, destination_id=destination_id)
    session.add(mapping)
    await session.flush()
    return mapping, True


# ==========================================================================
# Basic commands
# ==========================================================================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start: show the welcome message and main menu (owner only)."""
    if await _reject_if_not_owner(update):
        return
    await update.message.reply_text(
        WELCOME_TEXT, reply_markup=build_main_menu_keyboard(), parse_mode="HTML"
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /id: reply with the current chat's Telegram ID and title.

    Works in any chat type (private, group, supergroup, channel) so the
    owner can add the bot to a channel/group and immediately retrieve its
    numeric chat ID for use with the Setup New Channel wizard.
    """
    chat = update.effective_chat
    await context.bot.send_message(
        chat_id=chat.id,
        text=f"🆔 <b>Chat ID:</b> <code>{chat.id}</code>\n📛 <b>Title:</b> {chat.title or chat.first_name or 'N/A'}",
        parse_mode="HTML",
    )


# ==========================================================================
# Channel post listener (the actual forwarding trigger)
# ==========================================================================


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fire on every new channel post; forward it if the channel is a registered source.

    This never raises: any failure is logged so a single bad post can never
    crash the bot's update loop.
    """
    post = update.channel_post
    if post is None:
        return

    try:
        await process_new_post(context.bot, post.chat_id, post.message_id)
    except Exception:  # noqa: BLE001 - top-level safety net for the update loop
        logger.exception(
            "Unhandled error while processing new post: chat_id=%s message_id=%s",
            post.chat_id,
            post.message_id,
        )


# ==========================================================================
# Conversation: Setup New Channel (source -> destination mapping wizard)
# ==========================================================================


async def setup_new_channel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: prompt the owner to pick or register a source channel."""
    if await _reject_if_not_owner(update):
        return END
    await update.callback_query.answer()
    context.user_data.clear()

    async with get_session() as session:
        stmt = select(SourceChannel).where(
            SourceChannel.owner_id == settings.owner_id, SourceChannel.is_active.is_(True)
        ).order_by(SourceChannel.created_at.desc())
        sources = list((await session.execute(stmt)).scalars().all())

    context.user_data[UserDataKey.LIST_PAGE_INDEX] = 0
    text = (
        "🔗 <b>Setup New Channel</b>\n\n"
        "Step 1 of 2: choose a <b>Source</b>.\n\n"
        "Forward any post from the channel you want as the source, or send its "
        "numeric Chat ID / @username. You can also pick one already registered below."
    )
    await update.callback_query.edit_message_text(
        text, reply_markup=build_source_selection_keyboard(sources, page=0), parse_mode="HTML"
    )
    return ConversationState.MAPPING_SELECT_SOURCE


async def mapping_paginate_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Prev/Next pagination while selecting a source."""
    query = update.callback_query
    await query.answer()
    page = context.user_data.get(UserDataKey.LIST_PAGE_INDEX, 0)
    page += 1 if query.data == CallbackData.PAGE_NEXT else -1
    page = max(0, page)
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = page

    async with get_session() as session:
        stmt = select(SourceChannel).where(
            SourceChannel.owner_id == settings.owner_id, SourceChannel.is_active.is_(True)
        ).order_by(SourceChannel.created_at.desc())
        sources = list((await session.execute(stmt)).scalars().all())

    await query.edit_message_reply_markup(reply_markup=build_source_selection_keyboard(sources, page=page))
    return ConversationState.MAPPING_SELECT_SOURCE


async def mapping_source_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle picking an already-registered source via inline button."""
    query = update.callback_query
    await query.answer()
    _prefix, source_id = CallbackData.parse(query.data)
    if source_id is None:
        await query.edit_message_text("⚠️ Invalid selection. Please try again.")
        return ConversationState.MAPPING_SELECT_SOURCE

    async with get_session() as session:
        source = await session.get(SourceChannel, source_id)
        if source is None:
            await query.edit_message_text("⚠️ That source no longer exists.")
            return ConversationState.MAPPING_SELECT_SOURCE
        context.user_data[UserDataKey.MAPPING_SOURCE_ID] = source.id
        source_label = format_chat_label(source.title, source.chat_id)

    return await _prompt_for_destination(update, context, source_label)


async def mapping_source_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle a forwarded message or typed ID/@username registering a new source."""
    chat = await _resolve_target_chat(update, context)
    if chat is None:
        await update.message.reply_text(
            "⚠️ I couldn't identify that channel. Forward a post from it, or send its "
            "numeric Chat ID / @username. Use /id inside the channel to look it up.",
            reply_markup=build_cancel_keyboard(),
        )
        return ConversationState.MAPPING_SELECT_SOURCE

    if not await _validate_bot_is_admin(context.bot, chat):
        await update.message.reply_text(
            f"⚠️ I need to be an <b>admin</b> in \"{chat.title}\" before it can be a source. "
            "Please add me as admin and try again.",
            reply_markup=build_cancel_keyboard(),
            parse_mode="HTML",
        )
        return ConversationState.MAPPING_SELECT_SOURCE

    async with get_session() as session:
        source = await _get_or_create_source(session, chat.id, chat.title or "Untitled Source")
        context.user_data[UserDataKey.MAPPING_SOURCE_ID] = source.id
        source_label = format_chat_label(source.title, source.chat_id)

    log_action("register_source", update.effective_user.id, chat_id=chat.id)
    return await _prompt_for_destination(update, context, source_label)


async def _prompt_for_destination(update: Update, context: ContextTypes.DEFAULT_TYPE, source_label: str) -> int:
    """Show the destination-selection prompt after a source has been chosen."""
    async with get_session() as session:
        stmt = select(DestinationChannel).where(
            DestinationChannel.owner_id == settings.owner_id, DestinationChannel.is_active.is_(True)
        ).order_by(DestinationChannel.created_at.desc())
        destinations = list((await session.execute(stmt)).scalars().all())

    context.user_data[UserDataKey.LIST_PAGE_INDEX] = 0
    text = (
        f"✅ Source set: <b>{source_label}</b>\n\n"
        "Step 2 of 2: choose a <b>Destination</b>.\n\n"
        "Forward any post from the destination channel/group, or send its numeric "
        "Chat ID / @username. You can also pick one already registered below."
    )
    keyboard = build_destination_selection_keyboard(destinations, page=0)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
    return ConversationState.MAPPING_SELECT_DESTINATION


async def mapping_paginate_destination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Prev/Next pagination while selecting a destination."""
    query = update.callback_query
    await query.answer()
    page = context.user_data.get(UserDataKey.LIST_PAGE_INDEX, 0)
    page += 1 if query.data == CallbackData.PAGE_NEXT else -1
    page = max(0, page)
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = page

    async with get_session() as session:
        stmt = select(DestinationChannel).where(
            DestinationChannel.owner_id == settings.owner_id, DestinationChannel.is_active.is_(True)
        ).order_by(DestinationChannel.created_at.desc())
        destinations = list((await session.execute(stmt)).scalars().all())

    await query.edit_message_reply_markup(
        reply_markup=build_destination_selection_keyboard(destinations, page=page)
    )
    return ConversationState.MAPPING_SELECT_DESTINATION


async def _finalize_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE, destination: DestinationChannel) -> int:
    """Create the mapping for the current source + given destination, then ask to continue."""
    source_id = context.user_data.get(UserDataKey.MAPPING_SOURCE_ID)
    async with get_session() as session:
        mapping, created = await _get_or_create_mapping(session, source_id, destination.id)
        destination_label = format_chat_label(destination.title, destination.chat_id)

    log_action(
        "create_mapping", update.effective_user.id, source_id=source_id, destination_id=destination.id
    )
    status = "✅ Mapping created!" if created else "ℹ️ That mapping already existed and is now active."
    text = f"{status}\nDestination: <b>{destination_label}</b>\n\nAdd another destination for this source?"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=build_confirm_keyboard(), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=build_confirm_keyboard(), parse_mode="HTML")
    return ConversationState.MAPPING_CONFIRM


async def mapping_destination_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle picking an already-registered destination via inline button."""
    query = update.callback_query
    await query.answer()
    _prefix, destination_id = CallbackData.parse(query.data)
    if destination_id is None:
        await query.edit_message_text("⚠️ Invalid selection. Please try again.")
        return ConversationState.MAPPING_SELECT_DESTINATION

    async with get_session() as session:
        destination = await session.get(DestinationChannel, destination_id)
        if destination is None:
            await query.edit_message_text("⚠️ That destination no longer exists.")
            return ConversationState.MAPPING_SELECT_DESTINATION
        return await _finalize_mapping(update, context, destination)


async def mapping_destination_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle a forwarded message or typed ID/@username registering a new destination."""
    chat = await _resolve_target_chat(update, context)
    if chat is None:
        await update.message.reply_text(
            "⚠️ I couldn't identify that chat. Forward a post from it, or send its "
            "numeric Chat ID / @username.",
            reply_markup=build_cancel_keyboard(),
        )
        return ConversationState.MAPPING_SELECT_DESTINATION

    if not await _validate_bot_is_admin(context.bot, chat):
        await update.message.reply_text(
            f"⚠️ I need to be an <b>admin</b> (with post permission) in \"{chat.title}\" first. "
            "Please add me and try again.",
            reply_markup=build_cancel_keyboard(),
            parse_mode="HTML",
        )
        return ConversationState.MAPPING_SELECT_DESTINATION

    async with get_session() as session:
        destination = await _get_or_create_destination(session, chat.id, chat.title or "Untitled Destination")
        return await _finalize_mapping(update, context, destination)


async def mapping_confirm_add_another(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 'Confirm' (add another destination) at the end of a mapping round."""
    query = update.callback_query
    await query.answer()
    source_id = context.user_data.get(UserDataKey.MAPPING_SOURCE_ID)

    async with get_session() as session:
        source = await session.get(SourceChannel, source_id)
        source_label = format_chat_label(source.title, source.chat_id) if source else "your source"

    return await _prompt_for_destination(update, context, source_label)


async def mapping_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 'Cancel' (finish) at the end of a mapping round, ending the wizard."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎉 Setup complete! New posts in your source(s) will now be copied to the mapped destination(s).",
    )
    await query.message.reply_text("Main Menu:", reply_markup=build_main_menu_keyboard())
    context.user_data.clear()
    return END


async def conversation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generic fallback: cancel whichever conversation is currently active."""
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Cancelled.")
        await update.callback_query.message.reply_text("Main Menu:", reply_markup=build_main_menu_keyboard())
    elif update.message:
        await update.message.reply_text("❌ Cancelled.", reply_markup=build_main_menu_keyboard())
    return END


def build_setup_new_channel_conversation() -> ConversationHandler:
    """Construct the ConversationHandler for the Setup New Channel wizard."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(setup_new_channel_entry, pattern=f"^{CallbackData.MAIN_SETUP_NEW_CHANNEL}$")
        ],
        states={
            ConversationState.MAPPING_SELECT_SOURCE: [
                CallbackQueryHandler(mapping_source_selected, pattern=f"^{CallbackData.SELECT_SOURCE_PREFIX}:"),
                CallbackQueryHandler(
                    mapping_paginate_source, pattern=f"^({CallbackData.PAGE_PREV}|{CallbackData.PAGE_NEXT})$"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mapping_source_input),
            ],
            ConversationState.MAPPING_SELECT_DESTINATION: [
                CallbackQueryHandler(
                    mapping_destination_selected, pattern=f"^{CallbackData.SELECT_DESTINATION_PREFIX}:"
                ),
                CallbackQueryHandler(
                    mapping_paginate_destination, pattern=f"^({CallbackData.PAGE_PREV}|{CallbackData.PAGE_NEXT})$"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mapping_destination_input),
            ],
            ConversationState.MAPPING_CONFIRM: [
                CallbackQueryHandler(mapping_confirm_add_another, pattern=f"^{CallbackData.CONFIRM_YES}$"),
                CallbackQueryHandler(mapping_finish, pattern=f"^{CallbackData.CONFIRM_NO}$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(conversation_cancel, pattern=f"^{CallbackData.CANCEL}$")],
        conversation_timeout=900,
        name="setup_new_channel_conversation",
    )


# ==========================================================================
# Conversation: Delete Source
# ==========================================================================


async def delete_source_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: show the owner's sources for deletion."""
    if await _reject_if_not_owner(update):
        return END
    await update.callback_query.answer()
    context.user_data.clear()
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = 0

    async with get_session() as session:
        stmt = select(SourceChannel).where(SourceChannel.owner_id == settings.owner_id).order_by(
            SourceChannel.created_at.desc()
        )
        sources = list((await session.execute(stmt)).scalars().all())

    if not sources:
        await update.callback_query.edit_message_text(
            "You have no registered sources yet.", reply_markup=build_back_to_main_keyboard()
        )
        return END

    await update.callback_query.edit_message_text(
        "🗑️ <b>Delete Source</b>\n\nSelect a source to permanently remove. This also removes "
        "all of its destination mappings.",
        reply_markup=build_delete_source_keyboard(sources, page=0),
        parse_mode="HTML",
    )
    return ConversationState.DELETE_SOURCE_SELECT


async def delete_source_paginate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Prev/Next pagination while selecting a source to delete."""
    query = update.callback_query
    await query.answer()
    page = context.user_data.get(UserDataKey.LIST_PAGE_INDEX, 0)
    page += 1 if query.data == CallbackData.PAGE_NEXT else -1
    page = max(0, page)
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = page

    async with get_session() as session:
        stmt = select(SourceChannel).where(SourceChannel.owner_id == settings.owner_id).order_by(
            SourceChannel.created_at.desc()
        )
        sources = list((await session.execute(stmt)).scalars().all())

    await query.edit_message_reply_markup(reply_markup=build_delete_source_keyboard(sources, page=page))
    return ConversationState.DELETE_SOURCE_SELECT


async def delete_source_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle picking a source to delete: ask for confirmation."""
    query = update.callback_query
    await query.answer()
    _prefix, source_id = CallbackData.parse(query.data)
    if source_id is None:
        await query.edit_message_text("⚠️ Invalid selection.")
        return END

    async with get_session() as session:
        source = await session.get(SourceChannel, source_id)
        if source is None:
            await query.edit_message_text("⚠️ That source no longer exists.")
            return END
        label = format_chat_label(source.title, source.chat_id)

    context.user_data[UserDataKey.DELETE_SOURCE_ID] = source_id
    await query.edit_message_text(
        f"⚠️ Permanently delete source <b>{label}</b> and all its mappings?",
        reply_markup=build_confirm_keyboard(),
        parse_mode="HTML",
    )
    return ConversationState.DELETE_SOURCE_CONFIRM


async def delete_source_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle final confirmation of a source deletion."""
    query = update.callback_query
    await query.answer()

    if query.data == CallbackData.CONFIRM_NO:
        await query.edit_message_text("❌ Cancelled. Nothing was deleted.")
        context.user_data.clear()
        return END

    source_id = context.user_data.get(UserDataKey.DELETE_SOURCE_ID)
    async with get_session() as session:
        source = await session.get(SourceChannel, source_id)
        if source is not None:
            await session.delete(source)

    log_action("delete_source", update.effective_user.id, source_id=source_id)
    await query.edit_message_text("🗑️ Source deleted successfully.")
    await query.message.reply_text("Main Menu:", reply_markup=build_main_menu_keyboard())
    context.user_data.clear()
    return END


def build_delete_source_conversation() -> ConversationHandler:
    """Construct the ConversationHandler for the Delete Source flow."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_source_entry, pattern=f"^{CallbackData.MAIN_DELETE_SOURCE}$")],
        states={
            ConversationState.DELETE_SOURCE_SELECT: [
                CallbackQueryHandler(delete_source_selected, pattern=f"^{CallbackData.DELETE_SOURCE_PREFIX}:"),
                CallbackQueryHandler(
                    delete_source_paginate, pattern=f"^({CallbackData.PAGE_PREV}|{CallbackData.PAGE_NEXT})$"
                ),
            ],
            ConversationState.DELETE_SOURCE_CONFIRM: [
                CallbackQueryHandler(
                    delete_source_confirm, pattern=f"^({CallbackData.CONFIRM_YES}|{CallbackData.CONFIRM_NO})$"
                ),
            ],
        },
        fallbacks=[CallbackQueryHandler(conversation_cancel, pattern=f"^{CallbackData.CANCEL}$")],
        conversation_timeout=300,
        name="delete_source_conversation",
    )


# ==========================================================================
# Conversation: Remove Destination
# ==========================================================================


async def remove_destination_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: show the owner's destinations for removal."""
    if await _reject_if_not_owner(update):
        return END
    await update.callback_query.answer()
    context.user_data.clear()
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = 0

    async with get_session() as session:
        stmt = select(DestinationChannel).where(DestinationChannel.owner_id == settings.owner_id).order_by(
            DestinationChannel.created_at.desc()
        )
        destinations = list((await session.execute(stmt)).scalars().all())

    if not destinations:
        await update.callback_query.edit_message_text(
            "You have no registered destinations yet.", reply_markup=build_back_to_main_keyboard()
        )
        return END

    await update.callback_query.edit_message_text(
        "🚫 <b>Remove Destination</b>\n\nSelect a destination to permanently remove.",
        reply_markup=build_remove_destination_keyboard(destinations, page=0),
        parse_mode="HTML",
    )
    return ConversationState.REMOVE_DESTINATION_SELECT


async def remove_destination_paginate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Prev/Next pagination while selecting a destination to remove."""
    query = update.callback_query
    await query.answer()
    page = context.user_data.get(UserDataKey.LIST_PAGE_INDEX, 0)
    page += 1 if query.data == CallbackData.PAGE_NEXT else -1
    page = max(0, page)
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = page

    async with get_session() as session:
        stmt = select(DestinationChannel).where(DestinationChannel.owner_id == settings.owner_id).order_by(
            DestinationChannel.created_at.desc()
        )
        destinations = list((await session.execute(stmt)).scalars().all())

    await query.edit_message_reply_markup(reply_markup=build_remove_destination_keyboard(destinations, page=page))
    return ConversationState.REMOVE_DESTINATION_SELECT


async def remove_destination_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle picking a destination to remove: ask for confirmation."""
    query = update.callback_query
    await query.answer()
    _prefix, destination_id = CallbackData.parse(query.data)
    if destination_id is None:
        await query.edit_message_text("⚠️ Invalid selection.")
        return END

    async with get_session() as session:
        destination = await session.get(DestinationChannel, destination_id)
        if destination is None:
            await query.edit_message_text("⚠️ That destination no longer exists.")
            return END
        label = format_chat_label(destination.title, destination.chat_id)

    context.user_data[UserDataKey.REMOVE_DESTINATION_ID] = destination_id
    await query.edit_message_text(
        f"⚠️ Permanently remove destination <b>{label}</b>? It will stop receiving all forwarded posts.",
        reply_markup=build_confirm_keyboard(),
        parse_mode="HTML",
    )
    return ConversationState.REMOVE_DESTINATION_CONFIRM


async def remove_destination_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle final confirmation of a destination removal."""
    query = update.callback_query
    await query.answer()

    if query.data == CallbackData.CONFIRM_NO:
        await query.edit_message_text("❌ Cancelled. Nothing was removed.")
        context.user_data.clear()
        return END

    destination_id = context.user_data.get(UserDataKey.REMOVE_DESTINATION_ID)
    async with get_session() as session:
        destination = await session.get(DestinationChannel, destination_id)
        if destination is not None:
            await session.delete(destination)

    log_action("remove_destination", update.effective_user.id, destination_id=destination_id)
    await query.edit_message_text("🚫 Destination removed successfully.")
    await query.message.reply_text("Main Menu:", reply_markup=build_main_menu_keyboard())
    context.user_data.clear()
    return END


def build_remove_destination_conversation() -> ConversationHandler:
    """Construct the ConversationHandler for the Remove Destination flow."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(remove_destination_entry, pattern=f"^{CallbackData.MAIN_REMOVE_DESTINATION}$")
        ],
        states={
            ConversationState.REMOVE_DESTINATION_SELECT: [
                CallbackQueryHandler(
                    remove_destination_selected, pattern=f"^{CallbackData.REMOVE_DESTINATION_PREFIX}:"
                ),
                CallbackQueryHandler(
                    remove_destination_paginate, pattern=f"^({CallbackData.PAGE_PREV}|{CallbackData.PAGE_NEXT})$"
                ),
            ],
            ConversationState.REMOVE_DESTINATION_CONFIRM: [
                CallbackQueryHandler(
                    remove_destination_confirm, pattern=f"^({CallbackData.CONFIRM_YES}|{CallbackData.CONFIRM_NO})$"
                ),
            ],
        },
        fallbacks=[CallbackQueryHandler(conversation_cancel, pattern=f"^{CallbackData.CANCEL}$")],
        conversation_timeout=300,
        name="remove_destination_conversation",
    )


# ==========================================================================
# Main menu router (everything that isn't a conversation)
# ==========================================================================


async def _render_my_sources(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Render a page of the owner's registered sources."""
    async with get_session() as session:
        stmt = select(SourceChannel).where(SourceChannel.owner_id == settings.owner_id).order_by(
            SourceChannel.created_at.desc()
        )
        sources = list((await session.execute(stmt)).scalars().all())

    context.user_data[_CURRENT_VIEW_KEY] = _VIEW_SOURCES
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = page

    if not sources:
        await update.callback_query.edit_message_text(
            "📂 You have no registered sources yet.", reply_markup=build_back_to_main_keyboard()
        )
        return

    await update.callback_query.edit_message_text(
        f"📂 <b>My Sources</b> ({len(sources)} total)\n\n🟢 active · 🔴 disabled",
        reply_markup=build_my_sources_keyboard(sources, page=page),
        parse_mode="HTML",
    )


async def _render_my_destinations(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Render a page of the owner's registered destinations."""
    async with get_session() as session:
        stmt = select(DestinationChannel).where(DestinationChannel.owner_id == settings.owner_id).order_by(
            DestinationChannel.created_at.desc()
        )
        destinations = list((await session.execute(stmt)).scalars().all())

    context.user_data[_CURRENT_VIEW_KEY] = _VIEW_DESTINATIONS
    context.user_data[UserDataKey.LIST_PAGE_INDEX] = page

    if not destinations:
        await update.callback_query.edit_message_text(
            "📁 You have no registered destinations yet.", reply_markup=build_back_to_main_keyboard()
        )
        return

    await update.callback_query.edit_message_text(
        f"📁 <b>My Destinations</b> ({len(destinations)} total)\n\n🟢 active · 🔴 disabled",
        reply_markup=build_my_destinations_keyboard(destinations, page=page),
        parse_mode="HTML",
    )


async def _render_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render the Statistics screen with aggregate counts."""
    async with get_session() as session:
        active_sources = (
            await session.execute(
                select(func.count()).select_from(SourceChannel).where(SourceChannel.is_active.is_(True))
            )
        ).scalar_one()
        active_destinations = (
            await session.execute(
                select(func.count()).select_from(DestinationChannel).where(DestinationChannel.is_active.is_(True))
            )
        ).scalar_one()
        active_mappings = (
            await session.execute(
                select(func.count()).select_from(ChannelMapping).where(ChannelMapping.is_active.is_(True))
            )
        ).scalar_one()
        successful_forwards = (
            await session.execute(
                select(func.count()).select_from(ForwardLog).where(ForwardLog.success.is_(True))
            )
        ).scalar_one()
        failed_forwards = (
            await session.execute(
                select(func.count()).select_from(ForwardLog).where(ForwardLog.success.is_(False))
            )
        ).scalar_one()

    total_forwards = successful_forwards + failed_forwards
    success_rate = (successful_forwards / total_forwards * 100) if total_forwards else 0.0

    text = (
        "📊 <b>Statistics</b>\n\n"
        f"📂 Active Sources: <b>{active_sources}</b>\n"
        f"📁 Active Destinations: <b>{active_destinations}</b>\n"
        f"🔗 Active Mappings: <b>{active_mappings}</b>\n\n"
        f"✅ Successful Forwards: <b>{successful_forwards}</b>\n"
        f"❌ Failed Forwards: <b>{failed_forwards}</b>\n"
        f"📈 Success Rate: <b>{success_rate:.1f}%</b>"
    )
    await update.callback_query.edit_message_text(
        text, reply_markup=build_statistics_keyboard(), parse_mode="HTML"
    )


async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle every CallbackQueryHandler button not owned by an active conversation.

    Registered last (see register_handlers) so ConversationHandlers always
    get first refusal on updates belonging to their own active conversation.
    """
    query = update.callback_query
    if await _reject_if_not_owner(update):
        return

    data = query.data

    if data == CallbackData.MAIN_BACK:
        await query.answer()
        await query.edit_message_text(WELCOME_TEXT, reply_markup=build_main_menu_keyboard(), parse_mode="HTML")
        return

    if data == CallbackData.MAIN_SEND_CHAT_ID:
        await query.answer()
        await query.edit_message_text(
            "🆔 <b>Get a Chat ID</b>\n\n"
            "Add me to the channel or group (as admin), then send <code>/id</code> "
            "inside that chat and I'll reply with its numeric Chat ID.",
            reply_markup=build_back_to_main_keyboard(),
            parse_mode="HTML",
        )
        return

    if data in (CallbackData.MAIN_ADD_TO_CHANNEL, CallbackData.MAIN_ADD_TO_GROUP):
        await query.answer()
        target = "channel" if data == CallbackData.MAIN_ADD_TO_CHANNEL else "group"
        bot_username = context.bot.username
        await query.edit_message_text(
            f"➕ <b>Add Me To Your {target.title()}</b>\n\n"
            f"1. Open your {target} settings\n"
            f"2. Add <b>@{bot_username}</b> as an administrator "
            f"{'(with Post Messages permission) ' if target == 'channel' else ''}\n"
            "3. Come back and use <b>Setup New Channel</b> to register it.",
            reply_markup=build_back_to_main_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == CallbackData.MAIN_MY_SOURCES:
        await query.answer()
        await _render_my_sources(update, context, page=0)
        return

    if data == CallbackData.MAIN_MY_DESTINATIONS:
        await query.answer()
        await _render_my_destinations(update, context, page=0)
        return

    if data == CallbackData.MAIN_STATISTICS:
        await query.answer()
        await _render_statistics(update, context)
        return

    if data in (CallbackData.PAGE_PREV, CallbackData.PAGE_NEXT):
        await query.answer()
        current_view = context.user_data.get(_CURRENT_VIEW_KEY)
        page = context.user_data.get(UserDataKey.LIST_PAGE_INDEX, 0)
        page += 1 if data == CallbackData.PAGE_NEXT else -1
        page = max(0, page)
        if current_view == _VIEW_SOURCES:
            await _render_my_sources(update, context, page=page)
        elif current_view == _VIEW_DESTINATIONS:
            await _render_my_destinations(update, context, page=page)
        return

    prefix, row_id = CallbackData.parse(data)
    if prefix == CallbackData.VIEW_SOURCE_PREFIX and row_id is not None:
        await query.answer()
        async with get_session() as session:
            source = await session.get(SourceChannel, row_id)
        if source is None:
            await query.edit_message_text("⚠️ That source no longer exists.", reply_markup=build_back_to_main_keyboard())
            return
        status = "🟢 Active" if source.is_active else "🔴 Disabled"
        await query.edit_message_text(
            f"📂 <b>{source.title}</b>\nChat ID: <code>{source.chat_id}</code>\nStatus: {status}",
            reply_markup=build_back_to_main_keyboard(),
            parse_mode="HTML",
        )
        return

    if prefix == CallbackData.VIEW_DESTINATION_PREFIX and row_id is not None:
        await query.answer()
        async with get_session() as session:
            destination = await session.get(DestinationChannel, row_id)
        if destination is None:
            await query.edit_message_text(
                "⚠️ That destination no longer exists.", reply_markup=build_back_to_main_keyboard()
            )
            return
        status = "🟢 Active" if destination.is_active else "🔴 Disabled"
        await query.edit_message_text(
            f"📁 <b>{destination.title}</b>\nChat ID: <code>{destination.chat_id}</code>\nStatus: {status}",
            reply_markup=build_back_to_main_keyboard(),
            parse_mode="HTML",
        )
        return

    # Unknown / stale callback (e.g. from a message that predates a restart).
    await query.answer("This action is no longer available.", show_alert=True)


# ==========================================================================
# Error handler
# ==========================================================================


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Log any exception raised while processing an update.

    Registered via application.add_error_handler so a single failing handler
    can never crash the bot's polling/webhook loop.
    """
    logger.error("Unhandled exception while processing update: %s", update, exc_info=context.error)


# ==========================================================================
# Registration
# ==========================================================================


def register_handlers(application: Application) -> None:
    """
    Register every handler on the given Application, in precedence order.

    ConversationHandlers are added before the generic main_menu_router so
    that, while a user has an active conversation, its own state handlers
    get first refusal on matching updates (PTB only falls through to the
    next handler in the same group if the prior one's check_update() fails).

    Args:
        application: The configured telegram.ext.Application instance.
    """
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))

    application.add_handler(build_setup_new_channel_conversation())
    application.add_handler(build_delete_source_conversation())
    application.add_handler(build_remove_destination_conversation())

    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_channel_post))

    application.add_handler(CallbackQueryHandler(main_menu_router))

    application.add_error_handler(error_handler)

    logger.info("All handlers registered successfully.")
