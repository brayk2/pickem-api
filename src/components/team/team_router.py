from fastapi import APIRouter, Depends, Response

from src.components.team.team_service import TeamService

team_router = APIRouter(prefix="/teams", tags=["Teams"])


@team_router.get(
    "", responses={200: {"content": {"image/png": {}}}}, response_class=Response
)
async def get_spread(team_service: TeamService = Depends(TeamService.create)):
    return Response(content=team_service.get_team_image(), media_type="image/webp")
