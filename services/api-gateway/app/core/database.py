from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ─── Engine ───────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.ENVIRONMENT == "development",
    pool_size=10,
    max_overflow=20,
)

# ─── Session Factory ──────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─── Base Model ───────────────────────────────────────────────
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


# ─── Init ─────────────────────────────────────────────────────
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database connected")
    except Exception as e:
        logger.error("database connection failed", error=str(e))
        raise