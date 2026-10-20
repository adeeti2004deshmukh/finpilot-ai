from app.services.auth import get_current_user, ensure_actor
from app.models.entities import User
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import Transaction
from app.models.enums import TransactionType
from app.schemas.transactions import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.transactions import (
    categorize_transaction,
    require_transaction,
    require_user,
    validate_category,
)

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.get("", response_model=TransactionListResponse, summary="List and filter transactions")
def list_transactions(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2200),
    category: int | None = Query(default=None, gt=0),
    merchant: str | None = Query(default=None, min_length=1),
    transaction_type: TransactionType | None = None,
    user_id: int = Query(gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    query = select(Transaction)
    filters = []
    require_user(db, user_id)
    filters.append(Transaction.user_id == user_id)
    if month is not None:
        filters.append(extract("month", Transaction.date) == month)
    if year is not None:
        filters.append(extract("year", Transaction.date) == year)
    if category is not None:
        filters.append(Transaction.category_id == category)
    if merchant is not None:
        filters.append(Transaction.merchant.ilike(f"%{merchant}%"))
    if transaction_type is not None:
        filters.append(Transaction.transaction_type == transaction_type)
    if filters:
        query = query.where(*filters)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TransactionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED, summary="Create a transaction")
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> Transaction:
    payload = payload.model_copy(update={"user_id": ensure_actor(actor, payload.user_id)})
    require_user(db, payload.user_id)
    category_id = categorize_transaction(
        db, payload.merchant, payload.transaction_type, payload.category_id, user_id=actor.id
    )
    transaction = Transaction(**payload.model_dump(exclude={"category_id"}), category_id=category_id)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=TransactionResponse, summary="Get a transaction")
def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> Transaction:
    return require_transaction(db, transaction_id)


@router.put("/{transaction_id}", response_model=TransactionResponse, summary="Update a transaction")
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
) -> Transaction:
    transaction = require_transaction(db, transaction_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None and field not in {"category_id", "notes"}:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(transaction, field, value)

    if "merchant" in changes or "transaction_type" in changes:
        transaction.category_id = categorize_transaction(
            db,
            transaction.merchant,
            transaction.transaction_type,
            transaction.category_id, user_id=transaction.user_id,
        )
    else:
        validate_category(db, transaction.category_id, transaction.transaction_type)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a transaction")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)) -> Response:
    transaction = require_transaction(db, transaction_id)
    db.delete(transaction)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)