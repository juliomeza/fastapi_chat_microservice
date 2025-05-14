from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator # Added import
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True) # Set echo=False in production

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]: # Changed return type
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # For read-heavy app, explicit commit might not be needed here
            # await session.commit() # Uncomment if you have write operations that should auto-commit
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
