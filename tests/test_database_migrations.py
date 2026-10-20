"""Offline dialect checks are deliberately separate from real PostgreSQL tests."""
from io import StringIO
import re

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.database.base import Base


def test_postgresql_generated_migration_has_unique_constraint_names(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://postgres:postgres@127.0.0.1/finpilot")
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    tables = re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, flags=re.S)
    assert len(tables) == len(Base.metadata.tables) + 1  # Application tables plus alembic_version.
    for name, ddl in tables:
        constraints = re.findall(r"CONSTRAINT (\w+)", ddl)
        assert len(constraints) == len(set(constraints)), f"Duplicate constraint in {name}"
    for name in ("category_type", "alert_type", "alert_severity", "profile_risk_tolerance",
                 "goal_type", "investment_risk_tolerance", "transaction_type"):
        assert sql.count(f"CONSTRAINT {name} CHECK") == 1
    assert "NUMERIC(14, 2)" in sql and "TIMESTAMP WITH TIME ZONE" in sql


def test_sqlite_fresh_migration_roundtrip(tmp_path, monkeypatch):
    database_url = "sqlite:///" + (tmp_path / "migration_verification.db").as_posix()
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        assert "transactions" in inspect(engine).get_table_names()
        assert len(inspect(engine).get_check_constraints("categories")) == 1
        command.check(config)
        command.downgrade(config, "base")  # Only this test's new temporary file.
        assert inspect(engine).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert "goals" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_phase45_migration_preserves_legacy_demo_records(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "legacy_demo.db").as_posix()
    monkeypatch.setattr(settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "bf8c5f1a4a74")
    engine = create_engine(url)
    try:
        with engine.begin() as db:
            db.execute(text("INSERT INTO users (id,name,email,age) VALUES (42,'Aarav Sharma','aarav.sharma.demo@example.com',26)"))
            db.execute(text("INSERT INTO financial_profiles (id,user_id,monthly_income,other_income,current_savings,emergency_savings,monthly_debt_payment,total_debt,dependents,risk_tolerance,emergency_fund_target_months) VALUES (7,42,65000,0,120000,55000,5000,120000,0,'MODERATE',6)"))
            db.execute(text("INSERT INTO transactions (id,user_id,date,description,merchant,amount,transaction_type) VALUES (19,42,'2026-10-17','Existing expense','Existing merchant',500,'EXPENSE')"))
        command.upgrade(config, "head")
        with engine.connect() as db:
            user = db.execute(text("SELECT id,name,email,normalized_email,password_hash,is_demo,onboarding_completed FROM users WHERE id=42")).one()
            assert user[:4] == (42, "Aarav Sharma", "aarav.sharma.demo@example.com", "aarav.sharma.demo@example.com")
            assert user.password_hash is None and user.is_demo and user.onboarding_completed
            assert db.execute(text("SELECT user_id,amount FROM transactions WHERE id=19")).one() == (42, 500)
            assert db.execute(text("SELECT user_id,current_savings,emergency_savings FROM financial_profiles WHERE id=7")).one() == (42, 120000, 55000)
        command.check(config)
    finally:
        engine.dispose()
