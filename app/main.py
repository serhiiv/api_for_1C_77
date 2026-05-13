from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.messages import router as messages_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(messages_router)
