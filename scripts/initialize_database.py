"""Explicit operator command: migrate and initialize shared catalog, no user seeding."""
import argparse
from alembic import command
from alembic.config import Config
from app.database.session import SessionLocal
from app.services.catalog import ensure_catalog


def initialize(include_demo=False):
    command.upgrade(Config("alembic.ini"), "head")
    with SessionLocal() as db:
        ensure_catalog(db)
        db.commit()
    if include_demo:
        from seed import seed
        seed()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Explicitly create/update ONLY the read-only synthetic demo account")
    args = parser.parse_args()
    initialize(args.demo)
    print("Database initialization complete.")
