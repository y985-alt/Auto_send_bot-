from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def start_keyboard():
    """
    Main menu shown after /start
    """

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Send Main Channel Chat ID",
                callback_data="setup_main"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Add Me To Your Channel",
                url="https://t.me/share/url?url=https://t.me"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Add Me To Your Group",
                url="https://t.me/share/url?url=https://t.me"
            )
        ],
        [
            InlineKeyboardButton(
                "📂 My Channels",
                callback_data="my_channels"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Setup New Channels",
                callback_data="setup_new"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel Setup",
                callback_data="cancel_setup"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_setup"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="back_home"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def done_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Finish Setup",
                callback_data="finish_setup"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_setup"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def channels_keyboard(mappings: dict):
    keyboard = []

    if mappings:
        for main_channel in mappings.keys():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📢 {main_channel}",
                        callback_data=f"view_{main_channel}"
                    )
                ]
            )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="back_home"
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def manage_keyboard(main_chat: str):
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Duplicate",
                callback_data=f"adddup_{main_chat}"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Remove Main Channel",
                callback_data=f"remove_{main_chat}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅ Back",
                callback_data="my_channels"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)
