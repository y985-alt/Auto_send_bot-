"""
forwarder.py

Core forwarding engine: copies new posts from a registered SourceChannel to
every active DestinationChannel mapped to it.

Always uses bot.copy_message() (never forward_message()) so copied posts
appear native to the destination chat with no "Forwarded from" attribution.

Design:
    get_destinations()      -> Look up all active destinations for a source.
    copy_to_destination()   -> Attempt a single copy, with retry + error handling.
    forward_to_all()        -> Fan a single post out to every destination.
    forward_post()          -> Resolve destinations for a source and forward to all.
    process_new_post()      -> Entry point called by handlers.py's channel-post listener.
    disable_destination()   -> Soft-disable a destination the bot lost access to.
    log_forward_result()    -> Persist a ForwardLog row for statistics/debugging.

Every destination is attempted independently; a failure on one destination
never prevents attempts on the others.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telegram import Bot
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError, TimedOut, NetworkError

from database import get_session
from models import ChannelMapping, DestinationChannel, ForwardLog, SourceChannel
from utils import extract_error_message, retry_async

logger = logging.getLogger("bot.forwarder")


@dataclass
class ForwardAttemptResult:
    """
    Outcome of a single copy_message attempt to one destination.

    Attributes:
        destination_id: Primary key of the DestinationChannel row.
        destination_chat_id: Telegram chat ID of the destination.
        success: Whether the copy succeeded.
        error_message: Human-readable error description, if it failed.
        should_disable: Whether the destination should be soft-disabled
            (set when the bot has lost permission to post there).
    """

    destination_id: int
    destination_chat_id: int
    success: bool
    error_message: str | None = None
    should_disable: bool = False


async def get_destinations(session: AsyncSession, source_chat_id: int) -> list[DestinationChannel]:
    """
    Fetch every active DestinationChannel mapped to an active source.

    Args:
        session: An active AsyncSession.
        source_chat_id: The Telegram chat ID of the source channel that
            received a new post.

    Returns:
        A list of active DestinationChannel instances. Empty if the source
        is not registered, is disabled, or has no active mappings.
    """
    stmt = (
        select(DestinationChannel)
        .join(ChannelMapping, ChannelMapping.destination_id == DestinationChannel.id)
        .join(SourceChannel, ChannelMapping.source_id == SourceChannel.id)
        .where(
            SourceChannel.chat_id == source_chat_id,
            SourceChannel.is_active.is_(True),
            ChannelMapping.is_active.is_(True),
            DestinationChannel.is_active.is_(True),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_source(session: AsyncSession, source_chat_id: int) -> SourceChannel | None:
    """
    Fetch an active SourceChannel by its Telegram chat ID.

    Args:
        session: An active AsyncSession.
        source_chat_id: The Telegram chat ID to look up.

    Returns:
        The matching SourceChannel if it exists and is active, else None.
    """
    stmt = (
        select(SourceChannel)
        .options(selectinload(SourceChannel.mappings))
        .where(SourceChannel.chat_id == source_chat_id, SourceChannel.is_active.is_(True))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def disable_destination(session: AsyncSession, destination_id: int) -> None:
    """
    Soft-disable a destination, typically after the bot loses access to it.

    The row is not deleted so mapping history and statistics are preserved;
    the owner can see it flagged inactive under "My Destinations".

    Args:
        session: An active AsyncSession.
        destination_id: Primary key of the DestinationChannel to disable.
    """
    destination = await session.get(DestinationChannel, destination_id)
    if destination is None:
        return
    destination.is_active = False
    logger.warning(
        "Destination disabled due to loss of access: id=%s chat_id=%s",
        destination.id,
        destination.chat_id,
    )


async def copy_to_destination(
    bot: Bot,
    source_chat_id: int,
    message_id: int,
    destination: DestinationChannel,
) -> ForwardAttemptResult:
    """
    Attempt to copy a single message to a single destination, with retries.

    Args:
        bot: The active python-telegram-bot Bot instance.
        source_chat_id: Telegram chat ID the message originated from.
        message_id: The message ID within the source chat to copy.
        destination: The DestinationChannel to copy the message to.

    Returns:
        A ForwardAttemptResult describing success or the specific failure.
    """
    try:
        await retry_async(
            bot.copy_message,
            chat_id=destination.chat_id,
            from_chat_id=source_chat_id,
            message_id=message_id,
            retry_exceptions=(TimedOut, NetworkError),
        )
        return ForwardAttemptResult(
            destination_id=destination.id,
            destination_chat_id=destination.chat_id,
            success=True,
        )

    except Forbidden as exc:
        # Bot was removed/blocked/demoted in the destination chat.
        # This will not resolve itself on retry, so disable the destination.
        logger.warning(
            "Forbidden copying to destination chat_id=%s: %s", destination.chat_id, exc
        )
        return ForwardAttemptResult(
            destination_id=destination.id,
            destination_chat_id=destination.chat_id,
            success=False,
            error_message=extract_error_message(exc),
            should_disable=True,
        )

    except BadRequest as exc:
        # Malformed request or unsupported content for that chat type.
        # Not a permissions issue, so we log it but keep the destination active.
        logger.error(
            "BadRequest copying to destination chat_id=%s: %s", destination.chat_id, exc
        )
        return ForwardAttemptResult(
            destination_id=destination.id,
            destination_chat_id=destination.chat_id,
            success=False,
            error_message=extract_error_message(exc),
        )

    except RetryAfter as exc:
        # Should normally be absorbed inside retry_async; handled here as a
        # safety net in case all internal retry attempts were exhausted.
        logger.error(
            "FloodWait exhausted retries for destination chat_id=%s: %s",
            destination.chat_id,
            exc,
        )
        return ForwardAttemptResult(
            destination_id=destination.id,
            destination_chat_id=destination.chat_id,
            success=False,
            error_message=extract_error_message(exc),
        )

    except TelegramError as exc:
        logger.error(
            "TelegramError copying to destination chat_id=%s: %s", destination.chat_id, exc
        )
        return ForwardAttemptResult(
            destination_id=destination.id,
            destination_chat_id=destination.chat_id,
            success=False,
            error_message=extract_error_message(exc),
        )

    except Exception as exc:  # noqa: BLE001 - deliberate catch-all so one bad destination never halts the batch
        logger.exception(
            "Unexpected error copying to destination chat_id=%s", destination.chat_id
        )
        return ForwardAttemptResult(
            destination_id=destination.id,
            destination_chat_id=destination.chat_id,
            success=False,
            error_message=extract_error_message(exc),
        )


async def log_forward_result(
    session: AsyncSession,
    source_chat_id: int,
    message_id: int,
    result: ForwardAttemptResult,
) -> None:
    """
    Persist a ForwardLog row describing the outcome of one copy attempt.

    Args:
        session: An active AsyncSession.
        source_chat_id: Telegram chat ID the message originated from.
        message_id: The message ID within the source chat that was copied.
        result: The ForwardAttemptResult to record.
    """
    log_entry = ForwardLog(
        source_chat_id=source_chat_id,
        destination_chat_id=result.destination_chat_id,
        source_message_id=message_id,
        success=result.success,
        error_message=result.error_message,
    )
    session.add(log_entry)


async def forward_to_all(
    bot: Bot,
    session: AsyncSession,
    source_chat_id: int,
    message_id: int,
    destinations: list[DestinationChannel],
) -> list[ForwardAttemptResult]:
    """
    Copy a single message to every destination in the given list.

    Each destination is attempted independently: a Forbidden error disables
    that destination and logs the failure, but processing always continues
    on to the remaining destinations.

    Args:
        bot: The active python-telegram-bot Bot instance.
        session: An active AsyncSession.
        source_chat_id: Telegram chat ID the message originated from.
        message_id: The message ID within the source chat to copy.
        destinations: The destinations to copy the message to.

    Returns:
        A list of ForwardAttemptResult, one per destination, in the same order.
    """
    results: list[ForwardAttemptResult] = []

    for destination in destinations:
        result = await copy_to_destination(bot, source_chat_id, message_id, destination)

        if result.should_disable:
            await disable_destination(session, result.destination_id)

        await log_forward_result(session, source_chat_id, message_id, result)
        results.append(result)

    successes = sum(1 for r in results if r.success)
    logger.info(
        "Forwarded message_id=%s from source_chat_id=%s: %d/%d destinations succeeded.",
        message_id,
        source_chat_id,
        successes,
        len(results),
    )
    return results


async def forward_post(
    bot: Bot,
    session: AsyncSession,
    source_chat_id: int,
    message_id: int,
) -> list[ForwardAttemptResult]:
    """
    Resolve all active destinations for a source and forward one message to them.

    Args:
        bot: The active python-telegram-bot Bot instance.
        session: An active AsyncSession.
        source_chat_id: Telegram chat ID the message originated from.
        message_id: The message ID within the source chat to copy.

    Returns:
        A list of ForwardAttemptResult. Empty if the source has no active
        destinations mapped to it.
    """
    destinations = await get_destinations(session, source_chat_id)
    if not destinations:
        logger.debug(
            "No active destinations mapped for source_chat_id=%s; skipping.", source_chat_id
        )
        return []
    return await forward_to_all(bot, session, source_chat_id, message_id, destinations)


async def process_new_post(bot: Bot, source_chat_id: int, message_id: int) -> None:
    """
    Entry point invoked by handlers.py whenever a new post appears in any chat.

    Verifies the chat is a registered, active source before doing any work,
    then delegates to forward_post(). Opens and commits its own database
    session so this function is fully self-contained and safe to call
    directly from a MessageHandler callback.

    Args:
        bot: The active python-telegram-bot Bot instance.
        source_chat_id: Telegram chat ID the new post appeared in.
        message_id: The message ID of the new post.
    """
    async with get_session() as session:
        source = await get_active_source(session, source_chat_id)
        if source is None:
            # Not a registered source (or currently disabled) - nothing to do.
            return

        await forward_post(bot, session, source_chat_id, message_id)
