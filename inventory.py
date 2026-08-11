from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Account

async def reserve_account(session: AsyncSession, product_id: int):
    stmt = (
        select(Account)
        .where(Account.product_id == product_id, Account.status == "available")
        .order_by(Account.id)
        .with_for_update(skip_locked=True)
    )
    account = (await session.execute(stmt)).scalars().first()
    if account:
        account.status = "reserved"
        account.reserved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.flush()
    return account

async def release_account(session: AsyncSession, account_id: int):
    account = await session.get(Account, account_id, with_for_update=True)
    if account and account.status == "reserved":
        account.status = "available"
        account.reserved_at = None
        await session.flush()
        return True
    return False
