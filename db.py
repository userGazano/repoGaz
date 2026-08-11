from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session():
    async with SessionLocal() as session:
        yield session
