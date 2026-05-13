from fastapi import FastAPI

from app.config import get_settings
from app.health import router as health_router
from app.messages import router as messages_router

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(messages_router)
