from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL, logger

# ==========================================================
# SQLAlchemy Base
# ==========================================================

Base = declarative_base()

# ==========================================================
# Database Engine
# ==========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    future=True,
)

# ==========================================================
# Session Factory
# ==========================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

# ==========================================================
# Database Session
# ==========================================================

def get_session():
    """
    Returns a new SQLAlchemy session.
    """

    return SessionLocal()


# ==========================================================
# Create Tables
# ==========================================================

def create_tables():
    """
    Create all tables if they don't exist.
    """

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")

    except SQLAlchemyError as e:
        logger.error(f"Database Error: {e}")
        raise


# =================================================
