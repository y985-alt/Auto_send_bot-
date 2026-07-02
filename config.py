"""
config.py

Centralized configuration module for the Telegram forwarding bot.

Loads and validates all required environment variables using python-dotenv.
Every other module in this project imports configuration values from here.
No other module should call os.getenv() directly.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load environment variables from a .env file if present.
# In production (e.g. Heroku/Render), real environment variables take precedence
# and this call is a harmless no-op if no .env file exists.
load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


def _get_env(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    """
    Fetch an environment variable with optional required-ness enforcement.

    Args:
        name: Name of the environment variable.
        required: If True, raises ConfigError when the variable is missing or empty.
        default: Default value to use when the variable is not set and not required.

    Returns:
        The environment variable's value, or the default.

    Raises:
        ConfigError: If the variable is required but not set.
    """
    value = os.getenv(name, default)
    if required and (value is None or value.strip() == ""):
        raise ConfigError(
            f"Missing required environment variable: '{name}'. "
            f"Please set it in your .env file or process environment."
        )
    return value


def _get_int_env(name: str, *, required: bool = True, default: int | None = None) -> int:
    """
    Fetch an environment variable and coerce it to an integer.

    Args:
        name: Name of the environment variable.
        required: If True, raises ConfigError when missing.
        default: Default integer value if not required and not set.

    Returns:
        The parsed integer value.

    Raises:
        ConfigError: If the variable is required but missing, or not a valid integer.
    """
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        if required:
            raise ConfigError(f"Missing required environment variable: '{name}'.")
        return default  # type: ignore[return-value]

    try:
        return int(raw_value.strip())
    except ValueError as exc:
        raise ConfigError(
            f"Environment variable '{name}' must be an integer, got: '{raw_value}'."
        ) from exc


@dataclass(frozen=True)
class Settings:
    """
    Immutable application settings loaded from environment variables.

    Attributes:
        bot_token: Telegram Bot API token issued by @BotFather.
        database_url: Async-compatible SQLAlchemy connection string for PostgreSQL (Neon).
        owner_id: Telegram user ID authorized to manage the bot.
        log_level: Logging verbosity (e.g. DEBUG, INFO, WARNING, ERROR).
        max_retry_attempts: Maximum number of retry attempts for transient forward failures.
        retry_base_delay: Base delay in seconds used for exponential backoff.
    """

    bot_token: str
    database_url: str
    owner_id: int
    log_level: str = "INFO"
    max_retry_attempts: int = 3
    retry_base_delay: float = 1.5

    def __post_init__(self) -> None:
        """Validate cross-field constraints after initialization."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            raise ConfigError(
                f"LOG_LEVEL must be one of {sorted(valid_levels)}, got: '{self.log_level}'."
            )

        if not self.database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
            raise ConfigError(
                "DATABASE_URL must be a PostgreSQL connection string. "
                "For async SQLAlchemy, it should start with 'postgresql+asyncpg://'."
            )

        if self.owner_id <= 0:
            raise ConfigError(f"OWNER_ID must be a positive integer, got: {self.owner_id}.")


def _normalize_database_url(raw_url: str) -> str:
    """
    Ensure the database URL uses the asyncpg driver for SQLAlchemy's async engine.

    Neon and most providers issue plain 'postgresql://' or 'postgres://' URLs.
    This function rewrites them to 'postgresql+asyncpg://' so the async engine
    in database.py works without requiring manual configuration.

    Args:
        raw_url: The raw DATABASE_URL value from the environment.

    Returns:
        A normalized connection string compatible with SQLAlchemy's async engine.
    """
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_url


def load_settings() -> Settings:
    """
    Load, normalize, and validate all configuration from the environment.

    Returns:
        A fully validated Settings instance.

    Raises:
        ConfigError: If any required variable is missing or invalid.
    """
    bot_token = _get_env("BOT_TOKEN", required=True)
    raw_database_url = _get_env("DATABASE_URL", required=True)
    owner_id = _get_int_env("OWNER_ID", required=True)
    log_level = _get_env("LOG_LEVEL", required=False, default="INFO")
    max_retry_attempts = _get_int_env("MAX_RETRY_ATTEMPTS", required=False, default=3)
    retry_base_delay_raw = os.getenv("RETRY_BASE_DELAY", "1.5")

    try:
        retry_base_delay = float(retry_base_delay_raw)
    except ValueError as exc:
        raise ConfigError(
            f"RETRY_BASE_DELAY must be a float, got: '{retry_base_delay_raw}'."
        ) from exc

    return Settings(
        bot_token=bot_token,  # type: ignore[arg-type]
        database_url=_normalize_database_url(raw_database_url),  # type: ignore[arg-type]
        owner_id=owner_id,
        log_level=log_level.upper(),  # type: ignore[union-attr]
        max_retry_attempts=max_retry_attempts,
        retry_base_delay=retry_base_delay,
    )


def configure_logging(log_level: str) -> None:
    """
    Configure root logging for the entire application.

    Args:
        log_level: Logging level name (e.g. 'INFO', 'DEBUG').
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Silence noisy third-party loggers unless we're in DEBUG mode.
    if log_level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Module-level singleton, imported by every other module in the project.
try:
    settings: Settings = load_settings()
except ConfigError as error:
    # Fail fast and loudly at import time rather than deep inside a handler.
    print(f"[CONFIG ERROR] {error}", file=sys.stderr)
    raise

configure_logging(settings.log_level)

logger = logging.getLogger("bot.config")
logger.debug("Configuration loaded successfully. OWNER_ID=%s", settings.owner_id)
