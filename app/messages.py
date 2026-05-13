from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.rabbitmq import fetch_result, submit_request

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/process", status_code=status.HTTP_202_ACCEPTED)
async def process(body: Any) -> dict[str, Any]:
    """Прийняти JSON, відправити в чергу і повернути request_id."""
    try:
        request_id = await submit_request(body)
        return {
            "status": "accepted",
            "request_id": request_id,
            "result_endpoint": f"/messages/result/{request_id}",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue request",
        ) from exc


@router.get("/result/{request_id}")
async def result(request_id: str) -> dict[str, Any]:
    """Повернути результат для request_id, якщо воркер вже завершив обробку."""
    try:
        payload = await fetch_result(request_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch result",
        ) from exc

    if payload is None:
        return {"status": "pending", "request_id": request_id}

    return {"status": "ready", "request_id": request_id, "result": payload}
