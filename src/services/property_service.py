from src.config.base_service import BaseService
from src.models.new_db_models import PropertyModel
from src.util.injection import dependency, inject


@dependency
class PropertyService(BaseService):
    @inject
    def __init__(self):
        """
        Initializes the PropertyService.
        """
        pass

    def get_property(self, key: str, category: str) -> PropertyModel | None:
        """
        Retrieves a property value based on the key and category.

        :param key: The key for the property to retrieve.
        :param category: The category of the property.
        :return: PropertyModel instance if found, otherwise None.
        """
        self.logger.debug(
            f"Fetching property with key: '{key}', category: '{category}'"
        )

        # Fetch the property based on the key and category
        if query := PropertyModel.get_or_none(
            (PropertyModel.key == key) & (PropertyModel.category == category)
        ):
            self.logger.info(f"Property retrieved: {query.value}")
            return query

        self.logger.warning(
            f"Property with key '{key}' and category '{category}' not found."
        )

    def set_property(self, key: str, value: dict, category: str) -> PropertyModel:
        """
        Sets a property value based on the key and category.

        :param key: The key for the property to set.
        :param value: The value to be set for the property.
        :param category: The category of the property.
        :return: PropertyModel instance representing the set property.
        """
        self.logger.debug(
            f"Setting property with key: '{key}', category: '{category}', value: '{value}'"
        )
        prop, _ = PropertyModel.get_or_create(
            key=key, category=category, defaults={"value": value}
        )
        prop.value = value
        prop.save()
        self.logger.info(f"Property set successfully: {prop.value}")
        return prop
