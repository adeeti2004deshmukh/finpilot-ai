"""Opaque, revocable server-side sessions and authorization for financial routes."""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import re

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.models.entities import AuthSession, AuthThrottle, User, Transaction, Budget, Goal, MerchantRule

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(24))


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value: datetime):
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def check_csrf(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    allowed = {settings.frontend_url, settings.backend_url} - {""}
    if request.headers.get("x-finpilot-request") != "1" or (origin and origin not in allowed):
        raise HTTPException(status_code=403, detail="Request origin could not be verified")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    check_csrf(request)
    token = request.cookies.get(settings.session_cookie_name, "")
    session = db.get(AuthSession, token_hash(token)) if token else None
    if session is None or as_utc(session.expires_at) <= utcnow():
        raise HTTPException(status_code=401, detail="Sign in to continue")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


def establish_session(db: Session, request: Request, response: Response, user: User):
    old = request.cookies.get(settings.session_cookie_name)
    if old:
        previous = db.get(AuthSession, token_hash(old))
        if previous:
            db.delete(previous)
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=token_hash(token), user_id=user.id,
                       expires_at=utcnow() + timedelta(seconds=settings.session_ttl_seconds)))
    db.commit()
    response.set_cookie(settings.session_cookie_name, token, httponly=True,
                        secure=settings.app_env.lower() == "production", samesite=settings.session_cookie_samesite, path="/",
                        max_age=settings.session_ttl_seconds)
    response.headers["Cache-Control"] = "no-store"


def verify_password(password: str, encoded: str | None):
    try:
        return hasher.verify(encoded or dummy_hash, password) and encoded is not None
    except (VerificationError, InvalidHashError):
        return False


def throttle(db: Session, key: str, limit=10):
    now = utcnow()
    digest = token_hash(key)
    entry = db.get(AuthThrottle, digest)
    if entry is None:
        entry = AuthThrottle(key_hash=digest, attempts=0, window_started=now)
        db.add(entry)
    elif as_utc(entry.window_started) < now - timedelta(minutes=15):
        entry.attempts = 0
        entry.window_started = now
    if entry.attempts >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    entry.attempts += 1
    db.commit()


def ensure_actor(user: User, supplied_id: int | None):
    if supplied_id is not None and supplied_id != user.id:
        raise HTTPException(status_code=404, detail="Resource not found")
    return user.id


async def authorize_financial_request(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Protect legacy IDs as well as private record routes. No ID establishes identity."""
    for supplied in (request.path_params.get("user_id"), request.query_params.get("user_id")):
        if supplied is not None:
            try:
                ensure_actor(user, int(supplied))
            except ValueError:
                raise HTTPException(status_code=404, detail="Resource not found")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        calculation = request.method == "POST" and (request.url.path in {"/api/affordability/analyze", "/api/me/what-if"}
                       or re.fullmatch(r"/api/financial-plan/what-if/\d+", request.url.path) is not None)
        if user.is_demo and not calculation:
            raise HTTPException(status_code=403, detail="Demo account is read-only. Create an account to save your own data.")
        if "application/json" in request.headers.get("content-type", ""):
            try:
                body = await request.json()
            except ValueError:
                raise HTTPException(status_code=400, detail="Malformed JSON request") from None
            if isinstance(body, dict) and body.get("user_id") is not None:
                ensure_actor(user, body["user_id"])
    for parameter, model in (("transaction_id", Transaction), ("budget_id", Budget), ("goal_id", Goal), ("rule_id", MerchantRule)):
        raw_id = request.path_params.get(parameter)
        if raw_id is not None:
            try:
                entity = db.get(model, int(raw_id))
            except ValueError:
                raise HTTPException(status_code=404, detail="Resource not found")
            if entity is None or entity.user_id != user.id:
                raise HTTPException(status_code=404, detail="Resource not found")
    request.state.user = user
