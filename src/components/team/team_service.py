from src.config.base_service import BaseService
from src.util.injection import dependency


@dependency
class TeamService(BaseService):
    def get_team_image(self):
        # Imported here, not at module load: every cold start would pay for it.
        import imageio.v2 as iio

        return iio.imread("src/ravens.webp")
