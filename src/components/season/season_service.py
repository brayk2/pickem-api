from src.services.property_service import PropertyService
from src.util.injection import dependency, inject
from src.components.season.season_exceptions import (
    WeekNotSetException,
    YearNotSetException,
)
from src.config.base_service import BaseService


@dependency
class SeasonService(BaseService):
    @inject
    def __init__(self, property_service: PropertyService):
        """
        Initializes the SeasonService with a PropertyService instance.

        :param property_service: An instance of PropertyService used for interacting with the property table.
        """
        self.property_service = property_service

    def set_current_week(self, week: int) -> dict:
        """
        Sets the current week in the property table under the 'season' category.

        :param week: The week number to be set.
        :return: A dictionary containing the current week and year.
        """
        prop = self.property_service.set_property(
            key="week",
            value={"week": week},
            category="season",
        )
        self.logger.info(f"Current week set to {week}")

        year = self.get_current_year()["year"]
        return {"week": prop.value.get("week"), "year": year}

    def get_current_week_and_year(self) -> dict:
        """
        Gets the current week and year from the property table under the 'season' category.

        :return: A dictionary containing the current week and year.
        :raises WeekNotSetException: If the current week is not set in the property table.
        :raises YearNotSetException: If the current year is not set in the property table.
        """
        week_prop = self.property_service.get_property(key="week", category="season")
        year_prop = self.property_service.get_property(key="year", category="season")

        if not week_prop:
            self.logger.warning("Current week not set")
            raise WeekNotSetException()

        if not year_prop:
            self.logger.warning("Current year not set")
            raise YearNotSetException()

        self.logger.info(
            f"Current week: {week_prop.value['week']}, Current year: {year_prop.value['year']}"
        )
        return {"week": week_prop.value["week"], "year": year_prop.value["year"]}

    def set_current_year(self, year: int) -> dict:
        """
        Sets the current year in the property table under the 'season' category.

        :param year: The year to be set.
        :return: A dictionary containing the current year.
        """
        prop = self.property_service.set_property(
            key="year",
            value={"year": year},
            category="season",
        )
        self.logger.info(f"Current year set to {year}")
        return {"year": prop.value.get("year")}

    def get_current_year(self) -> dict:
        """
        Gets the current year from the property table under the 'season' category.

        :return: A dictionary containing the current year.
        :raises YearNotSetException: If the current year is not set in the property table.
        """
        year_prop = self.property_service.get_property(key="year", category="season")

        if not year_prop:
            self.logger.warning("Current year not set")
            raise YearNotSetException()

        self.logger.info(f"Current year retrieved: {year_prop.value['year']}")
        return {"year": year_prop.value["year"]}

    def get_season_info(self) -> None:
        """
        Placeholder for season info retrieval.

        :raises NotImplementedError: This feature is not yet implemented.
        """
        self.logger.info("Season info retrieval is not implemented yet.")
        raise NotImplementedError("This feature is not yet implemented.")
