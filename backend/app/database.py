import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# Find the project root regardless of the terminal's current directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load the private database configuration.
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Create a .env file in the project root."
    )


# Create the database engine.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# Create a factory for database sessions.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# Base class for all SQLAlchemy models.
class Base(DeclarativeBase):
    pass


# Supply one database session to an API request.
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()