import asyncio
import re
from typing import Optional

from telegram import Bot
from telegram.error import (
    TelegramError,
    RetryAfter,
    TimedOut,
    NetworkError,
    Forbidden,
    BadRequest,
)

from config import (
    logger,
    RETRY_COUNT,
    RETRY_DELAY,
)

# ==========================================================
# Chat ID Validator
# ==========================================================

def is_valid_chat_id(chat_id: str) -> bool:
    """
    Validates Telegram chat IDs.
    """

    if not chat_id:
        return False

    chat_id = str(chat_id).strip()

    pattern = r"^-?\d+$"

    return bool(re.fullmatch(pattern, chat_id))


# ==========================================================
# Safe Integer
# ==========================================================

def to_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ==========================================================
# Get Chat Info
# ==========================================================

async def get_chat(bot: Bot, chat_id: int):
    """
    Returns telegram.Chat object.
    """

    try:
        return await bot.get_chat(chat_id)

    except TelegramError as e:
        logger.error(f"get_chat({chat_id}) -> {e}")
        return None


# ==========================================================
# Check Bot Admin
# ==========================================================

async def is_bot_admin(bot: Bot, chat_id: int) -> bool:
    """
    Checks whether bot is admin.
    """

    try:
        me = await bot.get_me()

        member = await bot.get_chat_member(
            chat_id,
            me.id,
        )

        return member.status in (
            "administrator",
            "creator",
        )

    except Exception as e:
        logger.error(e)
        return False


# ==========================================================
# Safe Copy Message
# ==========================================================

async def safe_copy_message(
    bot: Bot,
    source_chat_id: int,
    destination_chat_id: int,
    message_id: int,
):
    """
    Copies a Telegram message with retry.
    """

    for attempt in range(RETRY_COUNT):

        try:

            return await bot.copy_message(
                chat_id=destination_chat_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
            )

        except RetryAfter as e:

            logger.warning(
                f"FloodWait {e.retry_after}s "
                f"for {destination_chat_id}"
            )

            await asyncio.sleep(e.retry_after)

        except (TimedOut, NetworkError):

            await asyncio.sleep(RETRY_DELAY)

        except Forbidden:

            logger.warning(
                f"Bot removed from {destination_chat_id}"
            )

            return None

        except BadRequest as e:

            logger.error(
                f"BadRequest: {destination_chat_id} -> {e}"
            )

            return None

        except TelegramError as e:

            logger.error(
                f"TelegramError: {destination_chat_id} -> {e}"
            )

            return None

        except Exception as e:

            logger.exception(e)

            return None

    return None


# ==========================================================
# Escape HTML
# ==========================================================

def escape_html(text: str) -> str:
    if text is None:
        return ""

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ==========================================================
# Success Text
# ==========================================================

def success(text: str) -> str:
    return f"✅ {text}"


# ==========================================================
# Error Text
# ==========================================================

def error(text: str)
