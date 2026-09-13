"""Database engine and session management."""

import os

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

from refit.models import User  # noqa: F401  (registers tables with SQLModel.metadata)

load_dotenv()

_engine = None

# TODO: single implicit user until Firebase Authentication is wired up (see Wiki
# Roadmap). Every recipe/log currently attributes to this user.
DEFAULT_FIREBASE_UID = "local-dev-user"


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
        # Neon (and most providers) hand out a plain "postgresql://" URL, which
        # SQLAlchemy defaults to the psycopg2 driver. We install psycopg (v3)
        # instead, so point SQLAlchemy at that driver explicitly.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        _engine = create_engine(database_url)
    return _engine


def create_db_and_tables():
    """Create all tables if they don't exist yet.

    MVP-only approach — replace with Alembic migrations before the schema
    needs to change against a database that already holds real data.
    """
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Session:
    return Session(get_engine())


def get_or_create_default_user(session: Session) -> User:
    user = session.query(User).filter_by(firebase_uid=DEFAULT_FIREBASE_UID).first()
    if user is None:
        user = User(firebase_uid=DEFAULT_FIREBASE_UID)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user
