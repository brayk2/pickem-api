from fastapi import APIRouter, Depends, Path
from src.components.standings.standings_dtos import StandingsHistoryDto, StandingsDto
from src.components.standings.standings_service import StandingsService


standings_router = APIRouter(prefix="/standings", tags=["Standings"])
standings_service = StandingsService()


@standings_router.get("/{year}/{week}/history", response_model=StandingsHistoryDto)
async def get_standings_history(
    year: int,
    week: int,
    # standings_service: StandingsService = Depends(StandingsService.create),
):
    return await standings_service.get_standings_history(year, week)


@standings_router.get(
    "/{year}/{week}",
    response_model=list[StandingsDto],
    summary="Get Standings for a Specific Week",
    responses={
        404: {"description": "The specified week or year does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_standings(
    year: int = Path(description="The year of the NFL season."),
    week: int = Path(description="The week number within the NFL season."),
    # service: StandingsService = Depends(StandingsService.create),
):
    """
    Retrieve the standings for a specific week in a given year.

    The standings are ranked based on the total score accumulated by each user, calculated from their correct picks
    multiplied by their confidence levels. The win percentage (`pct`) represents the ratio of correct picks to the total
    number of picks.

    **Example Response**:

    ```json
    [
        {
            "username": "player1",
            "rank": 1,
            "pct": 0.75,
            "score": 150
        },
        {
            "username": "player2",
            "rank": 2,
            "pct": 0.70,
            "score": 140
        }
    ]
    ```

    - **year**: The year of the NFL season.
    - **week**: The week number within the NFL season.

    Returns:
    - A list of standings for the specified week, each containing the username, rank, win percentage, and total score.
    """
    return await standings_service.get_standings_for_week(year=year, week=week)
