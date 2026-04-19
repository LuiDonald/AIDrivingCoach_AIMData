from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def _migrate(connection):
    """Add columns that may be missing in older databases."""
    try:
        connection.execute(text("ALTER TABLE sessions ADD COLUMN file_hash VARCHAR"))
    except Exception:
        pass
    try:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_file_hash ON sessions(file_hash)"))
    except Exception:
        pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate)
