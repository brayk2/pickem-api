from fastapi import APIRouter

ping_router = APIRouter(prefix="/ping", tags=["Ping"])


@ping_router.get("")
def ping():
    return {"healthy": True}
