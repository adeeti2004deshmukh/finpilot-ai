"""Production contracts without pretending that a cloud host/PostgreSQL is running."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.config import Settings, settings
from app.database.session import get_db, engine
from app.main import app
from app.models.entities import User, Transaction, Category
from app.services import request_security
from app.services.auth import check_csrf


def production(**values):
    return Settings(_env_file=None, app_env="production", database_url="postgresql://user:example-password@db.example.test/finpilot",
                    frontend_url="https://finance.example.test", **values)


@pytest.mark.parametrize("url", ["postgres://u:p@db.example.test/db", "postgresql://u:p@db.example.test/db", "postgresql+psycopg://u:p@db.example.test/db"])
def test_postgres_provider_urls_normalized(url):
    value = Settings(_env_file=None, database_url=url)
    assert value.database_url == "postgresql+psycopg://u:p@db.example.test/db"
    assert "u:p@" not in repr(value)


@pytest.mark.parametrize("overrides", [
    {"database_url": "sqlite:///local.db"}, {"frontend_url": "*"},
    {"frontend_url": "http://finance.example.test"}, {"frontend_url": "https://finance.example.test/path"},
    {"frontend_url": "https://finance.example.test?token=example"}, {"backend_url": "http://api.example.test"},
    {"frontend_url": "https://user:password@example.test"},
])
def test_bad_production_config_rejected(overrides):
    values = {"app_env": "production", "database_url": "postgresql://u:p@db.example.test/db", "frontend_url": "https://finance.example.test"}
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **{**values, **overrides})
    assert "u:p@" not in str(error.value)


def test_local_defaults_and_secure_cross_site_configuration(monkeypatch):
    for key in ("APP_ENV", "DATABASE_URL", "FRONTEND_URL", "BACKEND_URL", "SESSION_COOKIE_SAMESITE", "AI_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    local = Settings(_env_file=None)
    assert local.database_url.startswith("sqlite") and local.session_cookie_samesite == "lax" and local.ai_provider == "demo"
    assert production(session_cookie_samesite="none").session_cookie_samesite == "none"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, session_cookie_samesite="none")


def test_cors_exact_origin_and_credentials(client):
    allowed = client.options("/api/auth/login", headers={"Origin": settings.frontend_url, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type,X-FinPilot-Request"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == settings.frontend_url
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = client.options("/api/auth/login", headers={"Origin": "https://attacker.example.test", "Access-Control-Request-Method": "POST"})
    assert denied.status_code == 400 and "access-control-allow-origin" not in denied.headers


def test_host_header_does_not_establish_csrf_origin():
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [(b"host", b"attacker.example.test"),
             (b"origin", b"https://attacker.example.test"), (b"x-finpilot-request", b"1")], "scheme": "https", "server": ("attacker.example.test", 443)}
    with pytest.raises(HTTPException) as error:
        check_csrf(Request(scope))
    assert error.value.status_code == 403


def test_health_and_database_readiness(client, monkeypatch):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json() == {"status": "ready"}
    previous = app.dependency_overrides[get_db]
    def fail(*args):
        raise OperationalError("secret database connection", {}, RuntimeError("private credentials"))
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(execute=fail)
    try:
        response = client.get("/ready")
        assert response.status_code == 503 and response.json() == {"status": "unavailable"}
        assert "secret" not in response.text and "private" not in response.text
    finally:
        app.dependency_overrides[get_db] = previous


def test_request_limits_payload_and_malformed_json(client, user, monkeypatch):
    monkeypatch.setattr(settings, "max_request_bytes", 4096)
    response = client.post("/api/ai/chat", json={"message": "x" * 5000})
    assert response.status_code == 413 and "xxxxx" not in response.text
    malformed = client.post("/api/goals", content=b'{"user_id":', headers={"Content-Type": "application/json"})
    assert malformed.status_code in {400, 422}
    invalid = client.post("/api/ai/chat", json={"message": "hello", "user_id": user.id})
    assert invalid.status_code == 422


def test_production_simulation_limits_and_spoofed_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(request_security, "limits", request_security.RequestLimits())
    payload = {"monthly_contribution": "1000", "annual_rate_percent": "0", "months": 12}
    for _ in range(60):
        assert client.post("/api/simulate/sip", json=payload).status_code == 200
    denied = client.post("/api/simulate/sip", json=payload, headers={"X-Forwarded-For": "192.0.2.123"})
    assert denied.status_code == 429 and denied.headers["Retry-After"] == "60"
    assert client.get("/health").status_code == 200


def test_production_logs_and_headers_do_not_leak_exception(client, monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "production")
    def fail():
        raise RuntimeError("private upstream credentials and financial payload")
    original_routes = list(app.router.routes)
    app.add_api_route("/phase6-error-test", fail, methods=["GET"])
    try:
        response = client.get("/phase6-error-test")
        assert response.status_code == 500
        assert "private upstream" not in response.text + caplog.text
        assert "RuntimeError" in caplog.text
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "max-age" in response.headers["Strict-Transport-Security"]
    finally:
        app.router.routes[:] = original_routes
        app.openapi_schema = None


def test_secure_cookie_creation_and_deletion(db_session, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    monkeypatch.setattr(request_security, "limits", request_security.RequestLimits())
    previous = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, base_url="https://api.example.test", headers={"X-FinPilot-Request": "1"}) as client:
            response = client.post("/api/auth/register", json={"name": "Production Test", "email": "prod-cookie@example.com", "password": "Testing-Password-4567", "confirm_password": "Testing-Password-4567"})
            assert response.status_code == 201
            cookie = response.headers["set-cookie"].lower()
            assert "httponly" in cookie and "secure" in cookie and "samesite=none" in cookie
            assert "domain=" not in cookie
            assert client.get("/api/auth/me").status_code == 200
            logout = client.post("/api/auth/logout")
            assert "samesite=none" in logout.headers["set-cookie"].lower()
            assert client.get("/api/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_seed_refuses_non_demo_account(db_session, monkeypatch, user):
    import seed
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    user.email = seed.DEMO_EMAIL
    db_session.commit()
    with pytest.raises(RuntimeError, match="non-demo"):
        seed.seed()
    db_session.refresh(user)
    assert user.name == "Test User" and not user.is_demo


def test_initialize_catalog_without_users_or_financial_seed(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from scripts import initialize_database as init
    url = "sqlite:///" + (tmp_path / "initialization.db").as_posix()
    monkeypatch.setattr(settings, "database_url", url)
    temporary = create_engine(url)
    factory = sessionmaker(bind=temporary)
    monkeypatch.setattr(init, "SessionLocal", factory)
    try:
        init.initialize()
        init.initialize()
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(Category)) > 0
            assert db.scalar(select(func.count()).select_from(User)) == 0
            assert db.scalar(select(func.count()).select_from(Transaction)) == 0
    finally:
        temporary.dispose()


def test_sqlite_runtime_enforces_foreign_keys():
    if engine.dialect.name == "sqlite":
        with engine.connect() as db:
            assert db.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
