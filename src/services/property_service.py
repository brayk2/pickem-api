from src.config.base_service import BaseService
from src.models.db_models import PropertyModel
from src.util.injection import inject, dependency


@dependency
class PropertyService(BaseService):
    @inject
    def __init__(self):
        pass

    def get_oddsapi_quota(self):
        prop = PropertyModel.get(PropertyModel.key == "odds-api")
        return prop

    def set_oddsapi_quota(self, quota: dict):
        prop = PropertyModel.get(PropertyModel.key == "odds-api")
        prop.value = quota
        prop.save()

        return prop
