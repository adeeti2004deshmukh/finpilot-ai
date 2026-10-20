from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
pool_options = {} if connect_args else {"pool_size": 5, "max_overflow": 5, "pool_timeout": 5, "pool_recycle": 1800}
if not connect_args:
    connect_args = {"connect_timeout": 5}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True, hide_parameters=True, **pool_options)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
