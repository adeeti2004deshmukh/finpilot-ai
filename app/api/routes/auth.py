from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.session import get_db
from app.config import settings
from app.models.entities import User, FinancialProfile, AuthSession, Goal, InvestmentPreference
from app.models.enums import RiskTolerance
from app.schemas.auth import AuthUserResponse, LoginRequest, RegisterRequest, OnboardingRequest
from app.services.auth import check_csrf, get_current_user, establish_session, hasher, verify_password, throttle, token_hash, ensure_actor
from app.services.catalog import ensure_catalog

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthUserResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    check_csrf(request)
    throttle(db, f"register:{request.client.host if request.client else 'unknown'}", limit=20)
    email = str(payload.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account already uses this email. Sign in instead.")
    user = User(name=payload.name, email=email, normalized_email=email, age=None,
                password_hash=hasher.hash(payload.password.get_secret_value()), is_demo=False, onboarding_completed=False)
    try:
        db.add(user)
        db.flush()
        db.add(FinancialProfile(user_id=user.id, monthly_income=0, other_income=0, current_savings=0,
            emergency_savings=0, monthly_debt_payment=0, total_debt=0, dependents=0,
            risk_tolerance=RiskTolerance.MODERATE, emergency_fund_target_months=6, typical_essential_expenses=0))
        ensure_catalog(db)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to create this account. Try signing in.")
    establish_session(db, request, response, user)
    return user


@router.post("/login", response_model=AuthUserResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    check_csrf(request)
    throttle(db, f"login-ip:{request.client.host if request.client else 'unknown'}", limit=60)
    throttle(db, f"login-email:{payload.email}", limit=10)
    user = db.scalar(select(User).where(User.normalized_email == str(payload.email).lower()))
    if not verify_password(payload.password.get_secret_value(), user.password_hash if user else None) or user.is_demo:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(payload.password.get_secret_value())
    establish_session(db, request, response, user)
    return user


@router.get("/me", response_model=AuthUserResponse)
def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    check_csrf(request)
    token = request.cookies.get(settings.session_cookie_name)
    session = db.get(AuthSession, token_hash(token)) if token else None
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.app_env.lower() == "production", httponly=True, samesite=settings.session_cookie_samesite)
    response.headers["Cache-Control"] = "no-store"


@router.post("/demo", response_model=AuthUserResponse)
def demo(request: Request, response: Response, db: Session = Depends(get_db)):
    check_csrf(request)
    throttle(db, f"demo:{request.client.host if request.client else 'unknown'}", limit=30)
    user = db.scalar(select(User).where(User.is_demo.is_(True), User.normalized_email == "aarav.sharma.demo@example.com"))
    if user is None:
        raise HTTPException(status_code=503, detail="Demo is not available yet. Run the existing demo seed.")
    establish_session(db, request, response, user)
    return user


@router.post("/onboarding", response_model=AuthUserResponse)
def onboarding(payload: OnboardingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_demo:
        raise HTTPException(status_code=403, detail="Demo account is read-only")
    if user.onboarding_completed:
        raise HTTPException(status_code=409, detail="Onboarding is complete. Use Settings to update your profile.")
    ensure_actor(user, payload.user_id)
    profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user.id))
    for name, value in payload.model_dump(exclude={"user_id", "name", "age", "first_goal"}).items():
        setattr(profile, name, value)
    user.name, user.age = payload.name.strip(), payload.age
    if payload.first_goal:
        ensure_actor(user, payload.first_goal.user_id)
        db.add(Goal(**payload.first_goal.model_dump(exclude={"user_id"}), user_id=user.id))
    db.add(InvestmentPreference(user_id=user.id, risk_tolerance=payload.risk_tolerance,
                                liquidity_requirement="MEDIUM", preferred_time_horizon=10))
    user.onboarding_completed = True
    db.commit()
    return user
