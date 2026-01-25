"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Configure engine based on database type
_engine_options = {}

if settings.database_url.startswith("sqlite"):
    # SQLite: no pool settings needed
    _engine_options = {
        "connect_args": {"check_same_thread": False}
    }
else:
    # PostgreSQL: full connection pool
    _engine_options = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20
    }

engine = create_engine(settings.database_url, **_engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
