import boto3
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.config.base_service import BaseService
from src.components.admin.admin_exceptions import PropertyNotFoundException
from src.components.admin.admin_models import (
    CreateActionRequest,
    ActionType,
    CreateGroupResponse,
)
from src.components.week.week_models import WeekDto
from src.util.injection import dependency, inject
from src.components.property.property_service import PropertyService
from src.models.db_models import GroupModel, PropertyModel, WeekModel, SeasonModel


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

    def create_group(self, name: str, description: str) -> CreateGroupResponse:
        self.logger.info(f"Creating group: {name}")
        group = GroupModel.create(name=name, description=description)
        return CreateGroupResponse(
            id=group.id, name=group.name, description=group.description
        )

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

    def get_api_quota(self) -> dict:
        """
        The odds API quota as stored, `{"used": ..., "remaining": ...}`.

        :raises PropertyNotFoundException: If the quota has never been recorded.
        """
        prop = self.get_oddsapi_quota()
        if not prop:
            raise PropertyNotFoundException(key="odds-api", category="api")
        return prop.value

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
                state_machine_arn = state_machine.get("stateMachineArn")
                tags_response = client.list_tags_for_resource(
                    resourceArn=state_machine_arn
                )

                tags = tags_response.get("tags", [])
                if not any(
                    tag.get("key") == "ENVIRONMENT"
                    and tag.get("value") == self.settings.aws_env
                    for tag in tags
                ):
                    self.logger.info(
                        f"excluding state machine {state_machine_arn} with tags {tags}"
                    )
                    continue

                actions.append({**state_machine, "tags": tags})

        return actions

    def get_executions(self, state_machine_arn: str):
        executions = []

        client = boto3.client("stepfunctions")
        paginator = client.get_paginator("list_executions")

        for page in paginator.paginate(stateMachineArn=state_machine_arn):
            executions.extend(page.get("executions", []))

        return executions

    def _group_execution_history_events(self, events: list[dict]) -> dict:
        tasks = {}
        current_task = None

        for event in events:
            event_type = event.get("type")

            # skip execution events
            if event_type.startswith("Execution"):
                continue

            # begin new task if it is starting
            if "stateEnteredEventDetails" in event:
                current_task = event["stateEnteredEventDetails"]["name"]

            # add the event to the list for current task
            tasks[current_task] = [*tasks.get(current_task, []), event]

            if "stateExitedEventDetails" in event:
                current_task = None

        return tasks

    def get_execution(
        self,
        state_machine_arn: str,
        execution_arn: str,
        pagination_options: PaginationOptions,
    ):
        events = []
        self.logger.info(
            f"looking up execution state_machine={state_machine_arn}, execution={execution_arn}"
        )

        client = boto3.client("stepfunctions")
        paginator = client.get_paginator("get_execution_history")

        for page in paginator.paginate(executionArn=execution_arn):
            events.extend(page.get("events", []))

        return {
            "events": events,
            "tasks": self._group_execution_history_events(events=events),
        }

    def get_schedulers(self):
        schedules = []

        client = boto3.client("scheduler")
        paginator = client.get_paginator("list_schedules")

        for page in paginator.paginate(GroupName=self.settings.scheduler_group):
            for scheduler in page.get("Schedules", []):
                response = client.get_schedule(
                    GroupName=scheduler.get("GroupName"), Name=scheduler.get("Name")
                )
                response.pop("ResponseMetadata")
                schedules.append(response)

        return schedules

    def create_action(self, create_action_request: CreateActionRequest):
        client = boto3.client("lambda")
        client.get_function(FunctionName=create_action_request.arn)

    def trigger_action(self, state_machine_arn: str) -> dict:
        self.logger.info(
            f"triggering state machine, state_machine_arn={state_machine_arn}"
        )

        client = boto3.client("stepfunctions")
        return client.start_execution(stateMachineArn=state_machine_arn)
