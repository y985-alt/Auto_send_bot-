"""
bot.py

Application entry point. Wires together config, database, and handlers,
then starts the bot in long-polling mode.

Run with:
    python bot.py
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from config import settings
from database import check_connection, close_db, init_db
from handlers import register_handlers

logger = logging.getLogger("bot.main")


async def post_init(application: Application) -> None:
    """
    Run once after the Application is built but before polling starts.

    Verifies database connectivity, creates any missing tables, and logs
    the bot's identity so operators can confirm the correct token is loaded.

    Args:
        application: The running Application instance.
    """
    bot_info = await application.bot.get_me()
    logger.info("Authenticated as @%s (id=%s)", bot_info.username, bot_info.id)

    if not await check_connection():
        logger.error(
            "Could not connect to the database at startup. "
            "The bot will keep running, but all database-backed features will fail "
            "until connectivity is restored."
        )
    else:
        await init_db()
        logger.info("Database ready.")

    logger.info("Bot startup complete. Owner ID: %s", settings.owner_id)


async def post_shutdown(application: Application) -> None:
    """
    Run once as the Application is shutting down.

    Cleanly disposes of the database connection pool so no connections are
    left dangling when the process exits.

    Args:
        application: The Application instance that is shutting down.
    """
    await close_db()
    logger.info("Bot shutdown complete.")


def build_application() -> Application:
    """
    Construct and configure the Application, registering all handlers.

    Returns:
        A fully configured Application, ready to run_polling().
    """
    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    register_handlers(application)
    return application


def main() -> None:
    """Build the Application and start long-polling until interrupted."""
    application = build_application()

    logger.info("Starting bot in long-polling mode...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
