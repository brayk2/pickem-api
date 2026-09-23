import imageio.v2 as iio

from src.config.base_service import BaseService
from src.util.injection import dependency


@dependency
class TeamService(BaseService):
    def get_team_image(self):
        return iio.imread("src/ravens.webp")
