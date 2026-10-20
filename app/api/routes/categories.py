from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import Category
from app.models.enums import CategoryType
from app.schemas.categories import CategoryResponse

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse], summary="List transaction categories")
def list_categories(
    category_type: CategoryType | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
) -> list[Category]:
    query = select(Category).order_by(Category.type, Category.name)
    if category_type is not None:
        query = query.where(Category.type == category_type)
    return db.scalars(query).all()