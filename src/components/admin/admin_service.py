import boto3
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.config.base_service import BaseService
from src.models.dto.action_dto import CreateActionRequest, ActionType
from src.models.dto.week_dto import WeekDto
from src.util.injection import dependency, inject
from src.services.property_service import PropertyService
from src.models.new_db_models import PropertyModel, WeekModel, SeasonModel


class PaginationOptions(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    max_results: int = Field(default=10)
    next_token: str | None = Field(default=None)


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

        client = boto3.client("stepfunctions")
        paginator = client.get_paginator("list_state_machines")

        for page in paginator.paginate():
            for state_machine in page.get("stateMachines", []):
                tags_response = client.list_tags_for_resource(
                    resourceArn=state_machine.get("stateMachineArn")
                )
                actions.append({**state_machine, "tags": tags_response.get("tags")})

        return actions

    def get_executions(self, state_machine_arn: str):
        executions = []

        client = boto3.client("stepfunctions")
        paginator = client.get_paginator("list_executions")

        for page in paginator.paginate(stateMachineArn=state_machine_arn):
            executions.extend(page.get("executions", []))

        return executions

    def get_execution(
        self,
        state_machine_arn: str,
        execution_arn: str,
        pagination_options: PaginationOptions,
    ):
        self.logger.info(
            f"looking up execution state_machine={state_machine_arn}, execution={execution_arn}"
        )

        client = boto3.client("stepfunctions")
        response = client.get_execution_history(
            executionArn=execution_arn,
            **pagination_options.model_dump(by_alias=True, exclude_none=True),
        )

        return {
            "events": response.get("events", []),
            "nextToken": response.get("nextToken"),
        }

    def get_schedulers(self):
        schedules = []

        client = boto3.client("scheduler")
        paginator = client.get_paginator("list_schedules")

        for page in paginator.paginate():
            schedules.extend(page.get("Schedules", []))

        return schedules

    def create_action(self, create_action_request: CreateActionRequest):
        client = boto3.client("lambda")
        client.get_function(FunctionName=create_action_request.arn)
