from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import DATABASE_URL

# ==========================
# Database Connection
# ==========================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()

# ==========================
# Database Models
# ==========================

class MainChannel(Base):
    __tablename__ = "main_channels"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)

    duplicates = relationship(
        "DuplicateChannel",
        back_populates="main",
        cascade="all, delete"
    )


class DuplicateChannel(Base):
    __tablename__ = "duplicate_channels"

    id = Column(Integer, primary_key=True)
    main_id = Column(Integer, ForeignKey("main_channels.id"))
    chat_id = Column(BigInteger, unique=True, nullable=False)

    main = relationship("MainChannel", back_populates="duplicates")


# ==========================
# Create Tables
# ==========================

def create_tables():
    Base.metadata.create_all(bind=engine)


# ==========================
# Get Database Session
# ==========================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
