"""
models.py

SQLAlchemy ORM models for the Telegram forwarding bot.

Models:
    SourceChannel: A channel that new posts are copied FROM.
    DestinationChannel: A channel/group that posts are copied TO.
    ChannelMapping: Many-to-many link between a SourceChannel and a
        DestinationChannel, representing "this source forwards to this destination".
    ForwardLog: Audit trail of individual copy attempts, used for the
        Statistics feature and for debugging delivery failures.

All models inherit created_at / updated_at timestamps and an is_active flag
from shared mixins to avoid duplication.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TimestampMixin:
    """Adds created_at / updated_at columns, managed automatically by the DB."""

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ActiveMixin:
    """Adds an is_active flag used for soft-disabling records instead of deleting them."""

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SourceChannel(Base, TimestampMixin, ActiveMixin):
    """
    A Telegram channel that the bot monitors for new posts.

    Attributes:
        id: Internal primary key.
        chat_id: The Telegram chat ID of the source channel (negative for channels).
        title: Human-readable channel title, cached for display in menus.
        owner_id: Telegram user ID of the person who registered this source.
        mappings: All ChannelMapping rows linking this source to its destinations.
    """

    __tablename__ = "source_channels"
    __table_args__ = (
        UniqueConstraint("chat_id", name="uq_source_channels_chat_id"),
        Index("ix_source_channels_owner_id", "owner_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Source")
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    mappings: Mapped[list["ChannelMapping"]] = relationship(
        "ChannelMapping",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<SourceChannel id={self.id} chat_id={self.chat_id} title={self.title!r}>"


class DestinationChannel(Base, TimestampMixin, ActiveMixin):
    """
    A Telegram channel or group that receives copied posts.

    Attributes:
        id: Internal primary key.
        chat_id: The Telegram chat ID of the destination (negative for channels/groups).
        title: Human-readable destination title, cached for display in menus.
        owner_id: Telegram user ID of the person who registered this destination.
        mappings: All ChannelMapping rows linking this destination to its sources.
    """

    __tablename__ = "destination_channels"
    __table_args__ = (
        UniqueConstraint("chat_id", name="uq_destination_channels_chat_id"),
        Index("ix_destination_channels_owner_id", "owner_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Destination")
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    mappings: Mapped[list["ChannelMapping"]] = relationship(
        "ChannelMapping",
        back_populates="destination",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<DestinationChannel id={self.id} chat_id={self.chat_id} title={self.title!r}>"


class ChannelMapping(Base, TimestampMixin, ActiveMixin):
    """
    Links one SourceChannel to one DestinationChannel.

    A source can have many destinations, and (in principle) a destination
    could receive from multiple sources, so this is a many-to-many join table
    with its own surrogate key and an is_active flag so a single mapping can
    be disabled without deleting history.

    Attributes:
        id: Internal primary key.
        source_id: Foreign key to SourceChannel.id.
        destination_id: Foreign key to DestinationChannel.id.
        source: The related SourceChannel object.
        destination: The related DestinationChannel object.
    """

    __tablename__ = "channel_mappings"
    __table_args__ = (
        UniqueConstraint("source_id", "destination_id", name="uq_mapping_source_destination"),
        Index("ix_channel_mappings_source_id", "source_id"),
        Index("ix_channel_mappings_destination_id", "destination_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source_channels.id", ondelete="CASCADE"), nullable=False
    )
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destination_channels.id", ondelete="CASCADE"), nullable=False
    )

    source: Mapped["SourceChannel"] = relationship("SourceChannel", back_populates="mappings")
    destination: Mapped["DestinationChannel"] = relationship(
        "DestinationChannel", back_populates="mappings"
    )

    def __repr__(self) -> str:
        return f"<ChannelMapping id={self.id} source_id={self.source_id} destination_id={self.destination_id}>"


class ForwardLog(Base, TimestampMixin):
    """
    Audit record of a single copy_message attempt from a source post to a destination.

    Used to power the Statistics menu (success/failure counts) and to
    diagnose why a particular destination stopped receiving posts.

    Attributes:
        id: Internal primary key.
        source_chat_id: Telegram chat ID of the originating source.
        destination_chat_id: Telegram chat ID of the target destination.
        source_message_id: The original message ID in the source channel.
        success: Whether the copy succeeded.
        error_message: Populated with the exception text when success is False.
    """

    __tablename__ = "forward_logs"
    __table_args__ = (
        Index("ix_forward_logs_source_chat_id", "source_chat_id"),
        Index("ix_forward_logs_destination_chat_id", "destination_chat_id"),
        Index("ix_forward_logs_success", "success"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    destination_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return f"<ForwardLog id={self.id} {status} src={self.source_chat_id} dst={self.destination_chat_id}>"
