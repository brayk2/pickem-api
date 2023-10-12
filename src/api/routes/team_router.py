from fastapi import APIRouter, Response
from src.config.logger import get_logger
from src.models.db_models import TeamModel
from src.models.dto.dto import Spread
from src.services.spread_service import SpreadService
import imageio.v2 as iio

logger = get_logger(__name__)
spread_service = SpreadService()

team_router = APIRouter(prefix="/teams", tags=["Teams"])


@team_router.get(
    "", responses={200: {"content": {"image/png": {}}}}, response_class=Response
)
def get_spread():
    img = iio.imread("src/ravens.webp")
    return Response(content=img, media_type="image/webp")
