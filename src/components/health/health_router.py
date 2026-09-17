from fastapi import APIRouter

health_router = APIRouter(prefix="/ping", tags=["Ping"])


@health_router.get("")
async def ping():
    return {"healthy": True}
