import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.services.auth import get_current_user
from app.models.entities import FinancialProfile, User
from app.models.enums import RiskTolerance


@pytest.fixture
def postgresql_engine():
    """Opt-in real PostgreSQL tests, isolated in a unique disposable schema.

    No existing schema/table is dropped. The supplied role must create schemas.
    """
    database_url = os.environ.get("FINPILOT_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set FINPILOT_TEST_DATABASE_URL to run real PostgreSQL integration tests")
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        pytest.fail("FINPILOT_TEST_DATABASE_URL must use postgresql+psycopg")
    schema = "finpilot_test_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    schema_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(schema_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        # schema is generated locally above, never supplied by a caller.
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def test_engine(request):
    if os.environ.get("FINPILOT_TEST_DATABASE_URL"):
        engine = request.getfixturevalue("postgresql_engine")
        Base.metadata.create_all(engine)
        yield engine
        return
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Legacy financial regression fixtures authenticate only this test's user.
    # Authentication/isolation tests use a separate client without this override.
    def regression_actor():
        from sqlalchemy import select
        from fastapi import HTTPException
        actor = db_session.scalar(select(User).where(User.email == "test@example.com"))
        if actor is None:
            raise HTTPException(status_code=401, detail="Sign in to continue")
        return actor
    app.dependency_overrides[get_current_user] = regression_actor
    with TestClient(app, headers={"X-FinPilot-Request": "1"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session):
    user = User(name="Test User", email="test@example.com", age=29)
    db_session.add(user)
    db_session.flush()
    profile = FinancialProfile(
        user_id=user.id,
        monthly_income=65000,
        other_income=0,
        current_savings=120000,
        emergency_savings=55000,
        monthly_debt_payment=5000,
        total_debt=120000,
        dependents=0,
        risk_tolerance=RiskTolerance.MODERATE,
        emergency_fund_target_months=6,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(user)
    return user
