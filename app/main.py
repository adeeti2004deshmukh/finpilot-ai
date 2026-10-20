from dataclasses import asdict

import logging

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.request_security import RequestSecurityMiddleware

from app.api.routes import budgets, categories, dashboard, financial_intelligence, goals, merchant_rules, profiles, simulations, transactions, users
from app.config import settings
from app.services.auth import authorize_financial_request
from app.api.routes import auth, self_service, ai
from fastapi.exceptions import RequestValidationError
from app.demo_data import DEMO_AGE, DEMO_CITY, DEMO_CURRENCY, DEMO_PROFILE, DEMO_PROFILE_NAME
from app.financial_engine import (
    FinancialProfile,
    calculate_financial_summary,
    simulate_fd,
    simulate_rd,
    simulate_sip,
)
from app.schemas import (
    ContributionSimulationRequest,
    DemoResponse,
    FinancialProfileRequest,
    FinancialSummaryResponse,
    FixedDepositSimulationRequest,
    SimulationResponse,
)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-FinPilot-Request"],
)
app.add_middleware(RequestSecurityMiddleware)

logger = logging.getLogger(__name__)

for router in (
    transactions.router,
    profiles.router,
    users.router,
    categories.router,
    goals.router,
    budgets.router,
    dashboard.router,
    financial_intelligence.router,
    simulations.router,
    merchant_rules.router,
):
    app.include_router(router, dependencies=[] if router is simulations.router else [Depends(authorize_financial_request)])

app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(self_service.router, dependencies=[Depends(authorize_financial_request)])


@app.middleware("http")
async def private_response_headers(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        response = await unexpected_error_handler(request, exc)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if settings.app_env.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "The request conflicts with existing data"})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if settings.app_env.lower() == "production":
        logger.error("Unhandled API error (%s)", type(exc).__name__)
    else:
        logger.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _to_profile(request: FinancialProfileRequest) -> FinancialProfile:
    return FinancialProfile(**request.model_dump())


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/ready", include_in_schema=False)
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"}, headers={"Cache-Control": "no-store"})


@app.get("/api/v1/demo", response_model=DemoResponse)
def get_demo() -> DemoResponse:
    profile_request = FinancialProfileRequest(**asdict(DEMO_PROFILE))
    summary = calculate_financial_summary(DEMO_PROFILE)
    return DemoResponse(
        profile_name=DEMO_PROFILE_NAME,
        city=DEMO_CITY,
        age=DEMO_AGE,
        currency=DEMO_CURRENCY,
        profile=profile_request,
        summary=FinancialSummaryResponse(**asdict(summary)),
    )


@app.post("/api/v1/summary", response_model=FinancialSummaryResponse)
def financial_summary(request: FinancialProfileRequest) -> FinancialSummaryResponse:
    result = calculate_financial_summary(_to_profile(request))
    return FinancialSummaryResponse(**asdict(result))


@app.post("/api/v1/simulations/sip", response_model=SimulationResponse)
def sip_simulation(request: ContributionSimulationRequest) -> SimulationResponse:
    result = simulate_sip(request.monthly_contribution, request.annual_rate_percent, request.months)
    return SimulationResponse(**asdict(result))


@app.post("/api/v1/simulations/rd", response_model=SimulationResponse)
def rd_simulation(request: ContributionSimulationRequest) -> SimulationResponse:
    result = simulate_rd(request.monthly_contribution, request.annual_rate_percent, request.months)
    return SimulationResponse(**asdict(result))


@app.post("/api/v1/simulations/fd", response_model=SimulationResponse)
def fd_simulation(request: FixedDepositSimulationRequest) -> SimulationResponse:
    result = simulate_fd(
        request.principal,
        request.annual_rate_percent,
        request.months,
        request.compounds_per_year,
    )
    return SimulationResponse(**asdict(result))

@app.exception_handler(RequestValidationError)
async def safe_validation_errors(request: Request, exc: RequestValidationError):
    # Never echo submitted passwords or other sensitive inputs in validation errors.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})
