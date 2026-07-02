from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# ==========================================================
# Main Menu
# ==========================================================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "📥 Send Main Channel Chat ID",
                callback_data="add_source",
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Add Me To Your Channel",
                url="https://t.me/YourBotUsername?startchannel=true",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Add Me To Your Group",
                url="https://t.me/YourBotUsername?startgroup=true",
            )
        ],
        [
            InlineKeyboardButton(
                "📂 My Main Channels",
                callback_data="list_sources",
            )
        ],
        [
            InlineKeyboardButton(
                "📑 Destination Channels",
                callback_data="list_destinations",
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Link Destination",
                callback_data="link_destination",
            )
        ],
        [
            InlineKeyboardButton(
                "➖ Remove Destination",
                callback_data="remove_destination",
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Delete Main Channel",
                callback_data="delete_source",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="stats",
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Setup New Channel",
                callback_data="setup_new",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Close",
                callback_data="close",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ==========================================================
# Back Keyboard
# ==========================================================

def back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="back",
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==========================================================
# Yes / No Keyboard
# ==========================================================

def yes_no_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Yes",
                callback_data="yes",
            ),
            InlineKeyboardButton(
                "❌ No",
                callback_data="no",
            ),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==========================================================
# Cancel Keyboard
# ==========================================================

def cancel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel",
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==========================================================
# Source Action Keyboard
# ==========================================================

def source_action_keyboard(source_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Destination",
                callback_data=f"add_dest:{source_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "📋 View Destinations",
                callback_data=f"view_dest:{source_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Delete Source",
                callback_data=f"delete_source:{source_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="back",
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==========================================================
# Destination Action Keyboard
# ==========================================================

def destination_action_keyboard(destination_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Remove",
                callback_data=f"remove_dest:{destination_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="back",
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)
