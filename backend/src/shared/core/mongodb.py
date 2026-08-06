from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from src.shared.core.click_event import ClickEvent
from src.shared.core.config import settings


async def init_mongodb():
    """Initialize Beanie ODM with Motor async client."""
    client: AsyncIOMotorClient = AsyncIOMotorClient(  # type: ignore[var-annotated]
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
    )
    await init_beanie(
        database=client[settings.MONGODB_DB],
        document_models=[ClickEvent],
    )
