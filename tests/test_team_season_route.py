from fastapi.testclient import TestClient

from src.app import app
from src.components.league.league_permission import LeaguePermission
from src.components.standings.standings_service import StandingsService
from src.components.standings.team_season_stats import build_team_season_stats
from tests.test_team_season_stats import ROWS


class _FakeStandings:
    async def get_team_season_stats(self, year, week, league_id):
        return build_team_season_stats(ROWS, year=year, through_week=week)


def test_teams_route_serves_camel_case_through_the_week():
    app.dependency_overrides[StandingsService.create] = lambda: _FakeStandings()
    app.dependency_overrides[LeaguePermission.league_member] = lambda: None
    try:
        response = TestClient(app).get("/standings/1/2025/2/teams")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["throughWeek"] == 2
    assert body["teams"][0]["team"]["teamName"] == "Chiefs"
    assert body["teams"][0]["pointsWon"] == 8.0
    assert [w["result"] for w in body["teams"][0]["form"]] == ["COVERED", None]
    assert body["awards"]["moneyTeam"]["team"]["teamName"] == "Chiefs"
