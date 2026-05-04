import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.account import Account
from app.schemas.account import AccountRead

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    db: AsyncSession = Depends(get_db_session),
) -> list[Account]:
    result = await db.scalars(
        select(Account).where(Account.is_active.is_(True)).order_by(Account.account_code)
    )
    return list(result.all())
