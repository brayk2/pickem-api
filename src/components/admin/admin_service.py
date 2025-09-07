import boto3

from src.config.base_service import BaseService
from src.models.dto.action_dto import CreateActionRequest, ActionType
from src.models.dto.week_dto import WeekDto
from src.util.injection import dependency, inject
from src.services.property_service import PropertyService
from src.models.new_db_models import PropertyModel, WeekModel, SeasonModel


@dependency
class AdminService(BaseService):
    @inject
    def __init__(self, property_service: PropertyService):
        """
        Initializes the AdminService with a PropertyService instance.

        :param property_service: An instance of PropertyService used for interacting with the property table.
        """
        self.property_service = property_service

    def get_oddsapi_quota(self) -> PropertyModel:
        """
        Retrieves the odds API quota from the property table.

        :return: PropertyModel instance containing the odds API quota.
        """
        self.logger.debug("Fetching odds API quota from the property table.")
        prop = self.property_service.get_property(key="odds-api", category="api")
        if prop:
            self.logger.info(f"Odds API quota retrieved: {prop.value}")
        else:
            self.logger.warning("Odds API quota not found.")
        return prop

    def set_oddsapi_quota(self, quota: dict) -> PropertyModel:
        """
        Sets the odds API quota in the property table.

        :param quota: The quota data to be set.
        :return: PropertyModel instance representing the updated odds API quota.
        """
        self.logger.debug(f"Setting odds API quota: {quota}")
        prop = self.property_service.set_property(
            key="odds-api", value=quota, category="api"
        )
        self.logger.info(f"Odds API quota set successfully: {prop.value}")
        return prop

    def get_week_information(self, season: int) -> list[WeekDto]:
        return [
            WeekDto.from_orm(week)
            for week in WeekModel.select().where(WeekModel.season == season)
        ]

    def get_actions(self):
        actions = []

        client = boto3.client("lambda")
        paginator = client.get_paginator("list_functions")

        for page in paginator.paginate():
            actions.extend(page.get("Functions", []))
            # for lbda in page.get("Functions"):
            # actions.append(
            #     {
            #         "function_name": lbda.get("FunctionName"),
            #         "function_arn": lbda.get("FunctionArn"),
            #     }
            # )

        return actions

    def create_action(self, create_action_request: CreateActionRequest):
        client = boto3.client("lambda")
        client.get_function(FunctionName=create_action_request.arn)
