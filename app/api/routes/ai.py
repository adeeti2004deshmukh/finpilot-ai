from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import User
from app.services.auth import get_current_user
from app.services.ai.coach_service import chat
from app.services.ai.schemas import ChatRequest, ChatResponse
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["AI Coach"])


@router.get("/config")
def coach_config(actor: User = Depends(get_current_user)):
    return {"provider": settings.ai_provider}


@router.post("/chat", response_model=ChatResponse)
def coach_chat(payload: ChatRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # get_current_user also enforces CSRF. Demo users may read and simulate.
    return chat(db, actor.id, payload)
