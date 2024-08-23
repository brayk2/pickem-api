from fastapi import APIRouter, Response
from src.services.spread_service import SpreadService
import imageio.v2 as iio

spread_service = SpreadService()

team_router = APIRouter(prefix="/teams", tags=["Teams"])


@team_router.get(
    "", responses={200: {"content": {"image/png": {}}}}, response_class=Response
)
async def get_spread():
    img = iio.imread("src/ravens.webp")
    return Response(content=img, media_type="image/webp")
