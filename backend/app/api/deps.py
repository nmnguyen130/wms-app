from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """Provide a transactional asynchronous database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
