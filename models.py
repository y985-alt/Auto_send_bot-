from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base
from config import (
    SOURCE_TABLE,
    DESTINATION_TABLE,
    MAPPING_TABLE,
)

# ==========================================================
# Source Channels
# ==========================================================

class SourceChannel(Base):
    __tablename__ = SOURCE_TABLE

    id = Column(Integer, primary_key=True, index=True)

    owner_id = Column(
        BigInteger,
        nullable=False,
        index=True,
    )

    chat_id = Column(
        BigInteger,
        nullable=False,
        unique=True,
        index=True,
    )

    title = Column(
        String(255),
        nullable=True,
    )

    username = Column(
        String(255),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    destinations = relationship(
        "ChannelMapping",
        back_populates="source",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<SourceChannel(chat_id={self.chat_id}, "
            f"title={self.title})>"
        )


# ==========================================================
# Destination Channels / Groups
# ==========================================================

class DestinationChannel(Base):
    __tablename__ = DESTINATION_TABLE

    id = Column(Integer, primary_key=True, index=True)

    chat_id = Column(
        BigInteger,
        nullable=False,
        unique=True,
        index=True,
    )

    title = Column(
        String(255),
        nullable=True,
    )

    username = Column(
        String(255),
        nullable=True,
    )

    is_group = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    mappings = relationship(
        "ChannelMapping",
        back_populates="destination",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<DestinationChannel(chat_id={self.chat_id}, "
            f"title={self.title})>"
        )


# ==========================================================
# Source → Destination Mapping
# ==========================================================

class ChannelMapping(Base):
    __tablename__ = MAPPING_TABLE

    id = Column(Integer, primary_key=True)

    source_id = Column(
        Integer,
        ForeignKey(
            f"{SOURCE_TABLE}.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    destination_id = Column(
        Integer,
        ForeignKey(
            f"{DESTINATION_TABLE}.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    source = relationship(
        "SourceChannel",
        back_populates="destinations",
    )

    destination = relationship(
        "DestinationChannel",
        back_populates="mappings",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "destination_id",
            name="unique_source_destination",
        ),
    )

    def __repr__(self):
        return (
            f"<ChannelMapping("
            f"source={self.source_id}, "
            f"destination={self.destination_id})>"
  )
