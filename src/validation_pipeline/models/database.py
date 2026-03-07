from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from validation_pipeline.config import settings

engine = create_async_engine(settings.database_url, echo=(settings.environment == "dev"))
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Overridable session factory for background tasks (allows test injection)
_session_factory: async_sessionmaker = async_session


class Base(DeclarativeBase):
    pass


def set_session_factory(factory: async_sessionmaker) -> None:
    global _session_factory
    _session_factory = factory


def get_session_factory() -> async_sessionmaker:
    return _session_factory


async def get_session() -> AsyncSession:
    async with _session_factory() as session:
        yield session
