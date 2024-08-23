from src.config.logger import Logger
from src.config.settings import Settings


class BaseService:
    logger = Logger()
    settings = Settings()

    @classmethod
    def create(cls):
        return cls()
