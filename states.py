from telegram.ext import ConversationHandler

# ==========================================================
# Conversation States
# ==========================================================

(
    MAIN_MENU,

    WAIT_SOURCE_CHAT_ID,

    WAIT_SOURCE_TITLE,

    WAIT_DESTINATION_CHAT_ID,

    WAIT_DESTINATION_TITLE,

    WAIT_REMOVE_SOURCE,

    WAIT_REMOVE_DESTINATION,

    WAIT_SELECT_SOURCE,

    WAIT_CONFIRM_DELETE,

    WAIT_BROADCAST_MESSAGE,

    WAIT_SETTINGS,

    WAIT_CANCEL,

) = range(12)


# ==========================================================
# State Names (Optional)
# ==========================================================

STATE_NAMES = {
    MAIN_MENU: "MAIN_MENU",
    WAIT_SOURCE_CHAT_ID: "WAIT_SOURCE_CHAT_ID",
    WAIT_SOURCE_TITLE: "WAIT_SOURCE_TITLE",
    WAIT_DESTINATION_CHAT_ID: "WAIT_DESTINATION_CHAT_ID",
    WAIT_DESTINATION_TITLE: "WAIT_DESTINATION_TITLE",
    WAIT_REMOVE_SOURCE: "WAIT_REMOVE_SOURCE",
    WAIT_REMOVE_DESTINATION: "WAIT_REMOVE_DESTINATION",
    WAIT_SELECT_SOURCE: "WAIT_SELECT_SOURCE",
    WAIT_CONFIRM_DELETE: "WAIT_CONFIRM_DELETE",
    WAIT_BROADCAST_MESSAGE: "WAIT_BROADCAST_MESSAGE",
    WAIT_SETTINGS: "WAIT_SETTINGS",
    WAIT_CANCEL: "WAIT_CANCEL",
}


# ==========================================================
# Cancel Helper
# ==========================================================

END = ConversationHandler.END
