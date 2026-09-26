from fastapi import APIRouter, Request, status

from src.components.telemetry.telemetry_models import ClientEventBatch
from src.config.logger import Logger

telemetry_router = APIRouter(prefix="/telemetry", tags=["Telemetry"])
logger = Logger()


@telemetry_router.post("/client-events", status_code=status.HTTP_204_NO_CONTENT)
async def record_client_events(batch: ClientEventBatch, request: Request):
    """
    Writes what the browser reports into the same log group as the API's own
    request logs, so both sides of a failure can be queried together.
    """
    user_agent = (request.headers.get("user-agent") or "")[:300]
    for event in batch.events:
        logger.warning(
            "client event",
            extra={
                "fields": {
                    "type": "client_event",
                    "client_event": event.type,
                    **event.model_dump(exclude={"type"}, exclude_none=True),
                    "app_version": batch.app_version,
                    "session_id": batch.session_id,
                    "user_agent": user_agent,
                },
                "metrics": {"ClientReportedErrors": (1, "Count")},
            },
        )
