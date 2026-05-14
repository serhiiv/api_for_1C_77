from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

settings = get_settings()
api_key_header = APIKeyHeader(name=settings.api_key_header_name, auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    settings = get_settings()

    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key is not configured",
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )

    return api_key