from src.config.base_service import BaseService
from src.util.injection import inject, dependency


@dependency
class capitalize(${NAME})Service(BaseService):
    @inject
    def __init__(self):
        pass
