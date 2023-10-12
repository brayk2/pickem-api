from src.config.logger import get_logger
from src.config.settings import Settings


class BaseService:
    logger = get_logger(__name__)
    settings = Settings()
