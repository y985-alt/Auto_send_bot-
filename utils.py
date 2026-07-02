"""
utils.py

Shared utility functions used across handlers.py, forwarder.py, and keyboards.py.

Contains:
    - Permission checking (owner-only access control).
    - Chat ID parsing/validation.
    - Generic async retry-with-exponential-backoff helper.
    - Logging helpers for consistent structured log messages.
    - Small formatting/pagination helpers reused by the UI layer.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

from telegram.error import (
    BadRequest,
    Forbidden,
    NetworkError,
    RetryAfter,
    TelegramError,
    TimedOut,
)

from config import settings

logger = logging.getLogger("bot.utils")

T = TypeVar("T")

# Exceptions that are considered transient and worth retrying automatically.
TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (TimedOut, NetworkError)


# --------------------------------------------------------------------------
# Permission checking
# --------------------------------------------------------------------------


def is_owner(user_id: int | None) -> bool:
    """
    Check whether a Telegram user ID matches the configured bot owner.

    Args:
        user_id: The Telegram user ID to check, or None if unknown.

    Returns:
        True if the user is the bot owner, False otherwise.
    """
    if user_id is None:
        return False
    return user_id == settings.owner_id


def require_owner(user_id: int | None) -> None:
    """
    Raise a PermissionError if the given user is not the bot owner.

    Intended for use inside handlers as an early guard clause.

    Args:
        user_id: The Telegram user ID attempting an owner-only action.

    Raises:
        PermissionError: If the user is not the configured owner.
    """
    if not is_owner(user_id):
        logger.warning("Unauthorized access attempt by user_id=%s", user_id)
        raise PermissionError("This action is restricted to the bot owner.")


# --------------------------------------------------------------------------
# Chat ID validation
# --------------------------------------------------------------------------


def parse_chat_id(raw_text: str) -> int | None:
    """
    Parse a user-supplied string into a valid Telegram numeric chat ID.

    Telegram channel/group IDs are negative integers (typically prefixed
    with -100 for channels/supergroups). This does not resolve @usernames;
    use resolve_chat() for that, since it requires a live Bot instance.

    Args:
        raw_text: Raw text input from the user, e.g. "-1001234567890".

    Returns:
        The parsed integer chat ID, or None if the input is not a valid
        Telegram chat ID.
    """
    cleaned = raw_text.strip()
    if not cleaned:
        return None

    try:
        chat_id = int(cleaned)
    except ValueError:
        return None

    # Telegram channel/group/supergroup IDs are always negative.
    # Rule out obviously invalid values (e.g. positive user IDs).
    if chat_id >= 0:
        return None

    return chat_id


def is_valid_username_handle(raw_text: str) -> bool:
    """
    Check whether a string looks like a valid Telegram @username handle.

    Args:
        raw_text: Raw text input from the user, e.g. "@mychannel".

    Returns:
        True if the text matches Telegram's username format constraints.
    """
    cleaned = raw_text.strip()
    if not cleaned.startswith("@"):
        return False
    handle = cleaned[1:]
    if not (5 <= len(handle) <= 32):
        return False
    return all(char.isalnum() or char == "_" for char in handle)


async def resolve_chat(bot: Any, identifier: str) -> Any | None:
    """
    Resolve a chat ID or @username into a live Telegram Chat object.

    Args:
        bot: The python-telegram-bot Bot instance.
        identifier: Either a numeric chat ID string or an @username handle.

    Returns:
        The resolved Chat object, or None if the chat could not be found
        or the bot lacks access to it.
    """
    target: str | int
    parsed_id = parse_chat_id(identifier)
    if parsed_id is not None:
        target = parsed_id
    elif is_valid_username_handle(identifier):
        target = identifier.strip()
    else:
        return None

    try:
        return await bot.get_chat(target)
    except TelegramError:
        logger.exception("Failed to resolve chat identifier: %s", identifier)
        return None


# --------------------------------------------------------------------------
# Retry / backoff helpers
# --------------------------------------------------------------------------


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int | None = None,
    base_delay: float | None = None,
    retry_exceptions: tuple[type[Exception], ...] = TRANSIENT_EXCEPTIONS,
    **kwargs: Any,
) -> T:
    """
    Execute an async callable with automatic retries and exponential backoff.

    Handles Telegram's RetryAfter (FloodWait) specially by sleeping for the
    exact duration Telegram requests. Other transient exceptions (network
    timeouts, connection errors) use exponential backoff: base_delay * 2^attempt.

    Args:
        func: The async function to call.
        *args: Positional arguments passed to func.
        max_attempts: Maximum number of attempts before giving up.
            Defaults to settings.max_retry_attempts.
        base_delay: Base delay in seconds for exponential backoff.
            Defaults to settings.retry_base_delay.
        retry_exceptions: Exception types (besides RetryAfter) that should
            trigger a retry rather than propagate immediately.
        **kwargs: Keyword arguments passed to func.

    Returns:
        The return value of func on success.

    Raises:
        Exception: Re-raises the last encountered exception if all attempts
            are exhausted, or immediately for non-retryable exceptions
            (e.g. Forbidden, BadRequest).
    """
    attempts = max_attempts if max_attempts is not None else settings.max_retry_attempts
    delay = base_delay if base_delay is not None else settings.retry_base_delay

    last_exception: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)
        except RetryAfter as flood_wait:
            wait_seconds = float(flood_wait.retry_after) + 0.5
            logger.warning(
                "FloodWait triggered on attempt %d/%d. Sleeping %.1fs.",
                attempt,
                attempts,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            last_exception = flood_wait
        except retry_exceptions as transient_error:  # type: ignore[misc]
            backoff = delay * (2 ** (attempt - 1))
            logger.warning(
                "Transient error on attempt %d/%d: %s. Retrying in %.1fs.",
                attempt,
                attempts,
                transient_error,
                backoff,
            )
            await asyncio.sleep(backoff)
            last_exception = transient_error
        except (Forbidden, BadRequest):
            # Not retryable: permission or request-shape problems won't
            # resolve themselves by waiting. Let the caller handle them.
            raise

    logger.error("All %d retry attempts exhausted.", attempts)
    if last_exception is not None:
        raise last_exception
    raise TelegramError("retry_async exhausted all attempts with no captured exception.")


# --------------------------------------------------------------------------
# Logging helpers
# --------------------------------------------------------------------------


def log_action(action: str, user_id: int | None = None, **details: Any) -> None:
    """
    Emit a consistently formatted info-level log line for an owner action.

    Args:
        action: Short description of the action, e.g. "add_source".
        user_id: The Telegram user ID performing the action, if applicable.
        **details: Additional key-value context to include in the log line.
    """
    extra_context = " ".join(f"{key}={value}" for key, value in details.items())
    logger.info("ACTION=%s user_id=%s %s", action, user_id, extra_context)


def extract_error_message(exc: Exception) -> str:
    """
    Produce a short, human-readable error message from an exception.

    Truncated to keep it safe for storage in ForwardLog.error_message
    (which has a 500-character column limit) and for display in Telegram
    messages.

    Args:
        exc: The exception to describe.

    Returns:
        A truncated string representation of the exception.
    """
    message = f"{type(exc).__name__}: {exc}"
    return message[:497] + "..." if len(message) > 500 else message


# --------------------------------------------------------------------------
# Formatting / pagination helpers
# --------------------------------------------------------------------------


def truncate(text: str, max_length: int = 60) -> str:
    """
    Truncate text to a maximum length, appending an ellipsis if shortened.

    Args:
        text: The text to truncate.
        max_length: Maximum number of characters to keep.

    Returns:
        The original text if short enough, otherwise a truncated version.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def chunk_list(items: list[T], size: int) -> list[list[T]]:
    """
    Split a list into consecutive chunks of a given size.

    Used by keyboards.py to paginate long lists of sources/destinations
    into pages of inline buttons.

    Args:
        items: The list to split.
        size: Maximum number of items per chunk.

    Returns:
        A list of chunks, each a list with at most `size` items.
    """
    if size <= 0:
        raise ValueError("Chunk size must be a positive integer.")
    return [items[i : i + size] for i in range(0, len(items), size)]


def format_chat_label(title: str, chat_id: int) -> str:
    """
    Build a consistent display label for a channel in menus/buttons.

    Args:
        title: The cached chat title.
        chat_id: The Telegram chat ID.

    Returns:
        A formatted label, e.g. "My Channel (-1001234567890)".
    """
    return f"{truncate(title, 40)} ({chat_id})"
