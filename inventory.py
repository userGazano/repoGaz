from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models import Account
RESERVATION_MINUTES = 15
async def reserve_account(
    session: AsyncSession,
    product_id: int,
) -> Account | None:
    """
    Атомарно выбирает случайную доступную единицу товара.
    FOR UPDATE + SKIP LOCKED защищает от ситуации,
    когда два покупателя одновременно получают один товар.
    """
    query = (
        select(Account)
        .where(
            Account.product_id == product_id,
            Account.status == "available",
        )
        .order_by(func.random())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(query)
    account = result.scalar_one_or_none()
    if account is None:
        return None
    account.status = "reserved"
    account.reserved_at = datetime.utcnow()
    await session.flush()
    return account
async def release_account(
    session: AsyncSession,
    account_id: int,
) -> bool:
    """
    Возвращает зарезервированный товар обратно в available.
    """
    account = await session.get(
        Account,
        account_id,
        with_for_update=True,
    )
    if account is None:
        return False
    if account.status != "reserved":
        return False
    account.status = "available"
    account.reserved_at = None
    await session.flush()
    return True
async def cleanup_expired_reservations(
    session: AsyncSession,
) -> int:
    """
    Освобождает зависшие резервы старше RESERVATION_MINUTES.
    """
    cutoff = datetime.utcnow() - timedelta(
        minutes=RESERVATION_MINUTES
    )
    query = (
        select(Account)
        .where(
            Account.status == "reserved",
            Account.reserved_at.is_not(None),
            Account.reserved_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(query)
    accounts = result.scalars().all()
    count = 0
    for account in accounts:
        account.status = "available"
        account.reserved_at = None
        count += 1
    await session.flush()
    return count
