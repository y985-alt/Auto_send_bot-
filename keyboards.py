"""
keyboards.py

InlineKeyboardMarkup builders for every menu in the bot.

Every button's callback_data comes from states.CallbackData so that
handlers.py can parse it back with the exact same constants/prefixes.
This module contains no business logic and never touches the database
directly — it only renders lists of already-fetched model instances.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from models import DestinationChannel, SourceChannel
from states import CallbackData
from utils import chunk_list, format_chat_label

PAGE_SIZE = 5


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Build the main menu shown by /start.

    Returns:
        An InlineKeyboardMarkup with every top-level bot feature.
    """
    rows = [
        [InlineKeyboardButton("📌 Send Main Channel Chat ID", callback_data=CallbackData.MAIN_SEND_CHAT_ID)],
        [InlineKeyboardButton("➕ Add Me To Your Channel", callback_data=CallbackData.MAIN_ADD_TO_CHANNEL)],
        [InlineKeyboardButton("➕ Add Me To Your Group", callback_data=CallbackData.MAIN_ADD_TO_GROUP)],
        [InlineKeyboardButton("🔗 Setup New Channel", callback_data=CallbackData.MAIN_SETUP_NEW_CHANNEL)],
        [InlineKeyboardButton("📂 My Sources", callback_data=CallbackData.MAIN_MY_SOURCES)],
        [InlineKeyboardButton("📁 My Destinations", callback_data=CallbackData.MAIN_MY_DESTINATIONS)],
        [InlineKeyboardButton("📊 Statistics", callback_data=CallbackData.MAIN_STATISTICS)],
        [InlineKeyboardButton("🗑️ Delete Source", callback_data=CallbackData.MAIN_DELETE_SOURCE)],
        [InlineKeyboardButton("🚫 Remove Destination", callback_data=CallbackData.MAIN_REMOVE_DESTINATION)],
    ]
    return InlineKeyboardMarkup(rows)


def build_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """
    Build a single-button keyboard that returns the user to the main menu.

    Returns:
        An InlineKeyboardMarkup with one "Back" button.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back to Menu", callback_data=CallbackData.MAIN_BACK)]]
    )


# --------------------------------------------------------------------------
# Generic confirm / cancel
# --------------------------------------------------------------------------


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Build a keyboard with a single Cancel button, used mid-conversation.

    Returns:
        An InlineKeyboardMarkup with one "Cancel" button.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data=CallbackData.CANCEL)]]
    )


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Build a Yes/No confirmation keyboard.

    Returns:
        An InlineKeyboardMarkup with "Confirm" and "Cancel" buttons.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=CallbackData.CONFIRM_YES),
                InlineKeyboardButton("❌ Cancel", callback_data=CallbackData.CONFIRM_NO),
            ]
        ]
    )


# --------------------------------------------------------------------------
# Paginated selection lists (used by mapping setup, delete, remove flows)
# --------------------------------------------------------------------------


def _build_paginated_keyboard(
    labeled_rows: list[tuple[str, str]],
    page: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    """
    Build a paginated inline keyboard from pre-formatted (label, callback_data) pairs.

    Args:
        labeled_rows: List of (button_label, callback_data) tuples for every item.
        page: Zero-indexed page number currently being displayed.
        page_size: Number of items to show per page.

    Returns:
        An InlineKeyboardMarkup with one item per row, pagination controls,
        and a Cancel button.
    """
    pages = chunk_list(labeled_rows, page_size) if labeled_rows else [[]]
    page = max(0, min(page, len(pages) - 1))
    current_page_items = pages[page]

    rows = [[InlineKeyboardButton(label, callback_data=data)] for label, data in current_page_items]

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=CallbackData.PAGE_PREV))
    if page < len(pages) - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=CallbackData.PAGE_NEXT))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=CallbackData.CANCEL)])
    return InlineKeyboardMarkup(rows)


def build_source_selection_keyboard(
    sources: list[SourceChannel], page: int = 0
) -> InlineKeyboardMarkup:
    """
    Build a paginated keyboard for selecting a SourceChannel (used in mapping setup).

    Args:
        sources: List of SourceChannel instances owned by the requesting user.
        page: Zero-indexed page number to display.

    Returns:
        An InlineKeyboardMarkup listing each source as a selectable button.
    """
    labeled_rows = [
        (format_chat_label(source.title, source.chat_id), CallbackData.build(CallbackData.SELECT_SOURCE_PREFIX, source.id))
        for source in sources
    ]
    return _build_paginated_keyboard(labeled_rows, page)


def build_destination_selection_keyboard(
    destinations: list[DestinationChannel], page: int = 0
) -> InlineKeyboardMarkup:
    """
    Build a paginated keyboard for selecting a DestinationChannel (used in mapping setup).

    Args:
        destinations: List of DestinationChannel instances owned by the requesting user.
        page: Zero-indexed page number to display.

    Returns:
        An InlineKeyboardMarkup listing each destination as a selectable button.
    """
    labeled_rows = [
        (
            format_chat_label(destination.title, destination.chat_id),
            CallbackData.build(CallbackData.SELECT_DESTINATION_PREFIX, destination.id),
        )
        for destination in destinations
    ]
    return _build_paginated_keyboard(labeled_rows, page)


def build_delete_source_keyboard(sources: list[SourceChannel], page: int = 0) -> InlineKeyboardMarkup:
    """
    Build a paginated keyboard for choosing which source to delete.

    Args:
        sources: List of SourceChannel instances owned by the requesting user.
        page: Zero-indexed page number to display.

    Returns:
        An InlineKeyboardMarkup listing each source with a delete-targeted callback.
    """
    labeled_rows = [
        (
            f"🗑️ {format_chat_label(source.title, source.chat_id)}",
            CallbackData.build(CallbackData.DELETE_SOURCE_PREFIX, source.id),
        )
        for source in sources
    ]
    return _build_paginated_keyboard(labeled_rows, page)


def build_remove_destination_keyboard(
    destinations: list[DestinationChannel], page: int = 0
) -> InlineKeyboardMarkup:
    """
    Build a paginated keyboard for choosing which destination to remove.

    Args:
        destinations: List of DestinationChannel instances owned by the requesting user.
        page: Zero-indexed page number to display.

    Returns:
        An InlineKeyboardMarkup listing each destination with a remove-targeted callback.
    """
    labeled_rows = [
        (
            f"🚫 {format_chat_label(destination.title, destination.chat_id)}",
            CallbackData.build(CallbackData.REMOVE_DESTINATION_PREFIX, destination.id),
        )
        for destination in destinations
    ]
    return _build_paginated_keyboard(labeled_rows, page)


# --------------------------------------------------------------------------
# Read-only display lists (My Sources / My Destinations)
# --------------------------------------------------------------------------


def build_my_sources_keyboard(sources: list[SourceChannel], page: int = 0) -> InlineKeyboardMarkup:
    """
    Build a paginated read-only list of the user's registered sources.

    Args:
        sources: List of SourceChannel instances owned by the requesting user.
        page: Zero-indexed page number to display.

    Returns:
        An InlineKeyboardMarkup where each button opens a detail view for that source.
    """
    labeled_rows = [
        (
            f"{'🟢' if source.is_active else '🔴'} {format_chat_label(source.title, source.chat_id)}",
            CallbackData.build(CallbackData.VIEW_SOURCE_PREFIX, source.id),
        )
        for source in sources
    ]
    return _build_paginated_keyboard(labeled_rows, page)


def build_my_destinations_keyboard(
    destinations: list[DestinationChannel], page: int = 0
) -> InlineKeyboardMarkup:
    """
    Build a paginated read-only list of the user's registered destinations.

    Args:
        destinations: List of DestinationChannel instances owned by the requesting user.
        page: Zero-indexed page number to display.

    Returns:
        An InlineKeyboardMarkup where each button opens a detail view for that destination.
    """
    labeled_rows = [
        (
            f"{'🟢' if destination.is_active else '🔴'} {format_chat_label(destination.title, destination.chat_id)}",
            CallbackData.build(CallbackData.VIEW_DESTINATION_PREFIX, destination.id),
        )
        for destination in destinations
    ]
    return _build_paginated_keyboard(labeled_rows, page)


def build_statistics_keyboard() -> InlineKeyboardMarkup:
    """
    Build the keyboard shown alongside the Statistics report.

    Returns:
        An InlineKeyboardMarkup with a single "Back to Menu" button.
    """
    return build_back_to_main_keyboard()
