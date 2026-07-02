"""
states.py

Central definitions for:
    - ConversationHandler state constants (used by handlers.py).
    - Callback data string constants (shared by keyboards.py and handlers.py
      so button callbacks and their handlers never drift out of sync).
    - context.user_data key constants, used to pass data between steps of a
      conversation without relying on magic strings scattered across files.

Keeping these in one module guarantees keyboards.py and handlers.py always
agree on the exact string/int values they reference.
"""

from __future__ import annotations

from enum import IntEnum, auto

from telegram.ext import ConversationHandler

# Re-exported for convenience so handlers.py can import END from here too.
END = ConversationHandler.END


class ConversationState(IntEnum):
    """
    States used across all ConversationHandler flows in handlers.py.

    Each flow (add source, add destination, mapping, delete, remove) uses a
    distinct subset of these states. Sharing one enum avoids state-value
    collisions between independently-defined ConversationHandlers.
    """

    # --- Add Source flow ---
    ADD_SOURCE_AWAIT_INPUT = auto()
    ADD_SOURCE_CONFIRM = auto()

    # --- Add Destination flow ---
    ADD_DESTINATION_AWAIT_INPUT = auto()
    ADD_DESTINATION_CONFIRM = auto()

    # --- Setup New Channel (source -> destination mapping) flow ---
    MAPPING_SELECT_SOURCE = auto()
    MAPPING_SELECT_DESTINATION = auto()
    MAPPING_CONFIRM = auto()

    # --- Delete Source flow ---
    DELETE_SOURCE_SELECT = auto()
    DELETE_SOURCE_CONFIRM = auto()

    # --- Remove Destination flow ---
    REMOVE_DESTINATION_SELECT = auto()
    REMOVE_DESTINATION_CONFIRM = auto()


class UserDataKey:
    """
    String keys used to store transient conversation data in context.user_data.

    Using named constants instead of raw strings prevents typos from silently
    breaking a multi-step conversation.
    """

    PENDING_SOURCE_CHAT_ID = "pending_source_chat_id"
    PENDING_SOURCE_TITLE = "pending_source_title"

    PENDING_DESTINATION_CHAT_ID = "pending_destination_chat_id"
    PENDING_DESTINATION_TITLE = "pending_destination_title"

    MAPPING_SOURCE_ID = "mapping_source_id"
    MAPPING_DESTINATION_ID = "mapping_destination_id"

    DELETE_SOURCE_ID = "delete_source_id"
    REMOVE_DESTINATION_ID = "remove_destination_id"

    LIST_PAGE_INDEX = "list_page_index"


class CallbackData:
    """
    Callback_data string constants for every InlineKeyboardButton in keyboards.py.

    Callback data for buttons that reference a specific database row is built
    dynamically as f"{prefix}:{id}" using the *_PREFIX constants below, and
    parsed back out in handlers.py with the matching parse_* helper.
    """

    # --- Main menu ---
    MAIN_SEND_CHAT_ID = "main:send_chat_id"
    MAIN_ADD_TO_CHANNEL = "main:add_to_channel"
    MAIN_ADD_TO_GROUP = "main:add_to_group"
    MAIN_SETUP_NEW_CHANNEL = "main:setup_new_channel"
    MAIN_MY_SOURCES = "main:my_sources"
    MAIN_MY_DESTINATIONS = "main:my_destinations"
    MAIN_STATISTICS = "main:statistics"
    MAIN_DELETE_SOURCE = "main:delete_source"
    MAIN_REMOVE_DESTINATION = "main:remove_destination"
    MAIN_BACK = "main:back"

    # --- Generic navigation ---
    CANCEL = "nav:cancel"
    CONFIRM_YES = "nav:confirm_yes"
    CONFIRM_NO = "nav:confirm_no"
    PAGE_PREV = "nav:page_prev"
    PAGE_NEXT = "nav:page_next"

    # --- Dynamic selection prefixes (paired with a numeric row ID) ---
    SELECT_SOURCE_PREFIX = "select_source"
    SELECT_DESTINATION_PREFIX = "select_destination"
    DELETE_SOURCE_PREFIX = "delete_source"
    REMOVE_DESTINATION_PREFIX = "remove_destination"
    VIEW_SOURCE_PREFIX = "view_source"
    VIEW_DESTINATION_PREFIX = "view_destination"

    @staticmethod
    def build(prefix: str, row_id: int) -> str:
        """
        Build a dynamic callback_data string for a specific database row.

        Args:
            prefix: One of the *_PREFIX constants above.
            row_id: The primary key of the SourceChannel/DestinationChannel row.

        Returns:
            A callback_data string in the form "prefix:row_id".
        """
        return f"{prefix}:{row_id}"

    @staticmethod
    def parse(callback_data: str) -> tuple[str, int | None]:
        """
        Parse a dynamic callback_data string back into its prefix and row ID.

        Args:
            callback_data: The raw callback_data received from a CallbackQuery.

        Returns:
            A tuple of (prefix, row_id). row_id is None if the callback_data
            did not contain a valid trailing integer.
        """
        if ":" not in callback_data:
            return callback_data, None
        prefix, _, raw_id = callback_data.rpartition(":")
        try:
            return prefix, int(raw_id)
        except ValueError:
            return callback_data, None
