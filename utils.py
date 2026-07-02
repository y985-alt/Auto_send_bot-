from telegram import Bot
from telegram.error import TelegramError

from config import (
    INVALID_CHAT_ID,
    NOT_ADMIN
)


def is_chat_id(value: str) -> bool:
    """
    Validate Telegram chat ID.
    Channel/group IDs are usually negative and start with -100.
    """
    value = value.strip()

    if not value:
        return False

    if value.startswith("-"):
        return value[1:].isdigit()

    return value.isdigit()


def normalize_chat_id(value: str) -> int:
    """
    Convert chat id string to integer.
    """
    return int(value.strip())


async def check_bot_admin(bot: Bot, chat_id: int) -> tuple[bool, str]:
    """
    Verify that the bot is an administrator
    in the given channel/group.
    """

    try:
        me = await bot.get_me()

        member = await bot.get_chat_member(
            chat_id=chat_id,
            user_id=me.id
        )

        if member.status in ("administrator", "creator"):
            return True, ""

        return False, NOT_ADMIN

    except TelegramError:
        return False, INVALID_CHAT_ID

    except Exception:
        return False, INVALID_CHAT_ID


async def get_chat_title(bot: Bot, chat_id: int) -> str:
    """
    Return channel/group title.
    """

    try:
        chat = await bot.get_chat(chat_id)

        if chat.title:
            return chat.title

        if chat.full_name:
            return chat.full_name

        return str(chat_id)

    except Exception:
        return str(chat_id)


def format_mapping(main_chat: str, duplicates: list[int]) -> str:
    """
    Create a readable mapping message.
    """

    text = f"📢 Main Channel\n<code>{main_chat}</code>\n\n"

    if not duplicates:
        text += "No duplicate channels added."
        return text

    text += "📤 Duplicate Channels\n\n"

    for index, chat in enumerate(duplicates, start=1):
        text += f"{index}. <code>{chat}</code>\n"

    return text


def split_text(text: str, limit: int = 4000):
    """
    Split long Telegram messages.
    """

    if len(text) <= limit:
        return [text]

    parts = []

    while len(text) > limit:
        cut = text[:limit]

        pos = cut.rfind("\n")

        if pos == -1:
            pos = limit

        parts.append(text[:pos])

        text = text[pos:]

    if text:
        parts.append(text)

    return parts
