from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ─── Engine ───────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.ENVIRONMENT == "development",
    pool_size=5,
    max_overflow=10,
)

# ─── Session Factory ──────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ─── Dependency ───────────────────────────────────────────────
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
