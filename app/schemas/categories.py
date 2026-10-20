from datetime import datetime

from app.models.enums import CategoryType
from app.schemas.base import ORMModel


class CategoryResponse(ORMModel):
    id: int
    name: str
    type: CategoryType
    is_essential: bool
    created_at: datetime