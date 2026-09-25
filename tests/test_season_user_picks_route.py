from fastapi.testclient import TestClient

from src.app import app
from src.components.league.league_permission import LeaguePermission
from src.components.results.results_service import ResultsService


class _Token:
    sub = "brayden"


class _FakeResults:
    def __init__(self):
        self.asked_for = None

    async def get_user_season_results(self, year, league_id, username):
        self.asked_for = username
        return {"username": username, "picks": [], "rank": None, "totalScore": 0}


def _get(path):
    fake = _FakeResults()
    app.dependency_overrides[ResultsService.create] = lambda: fake
    app.dependency_overrides[LeaguePermission.league_member] = lambda: _Token()
    try:
        response = TestClient(app).get(path)
    finally:
        app.dependency_overrides.clear()
    return response, fake


def test_season_picks_default_to_the_caller():
    response, fake = _get("/results/1/2026/user-picks")
    assert response.status_code == 200
    assert fake.asked_for == "brayden"


def test_season_picks_can_be_read_for_another_member():
    response, fake = _get("/results/1/2026/user-picks?username=sam")
    assert response.status_code == 200
    assert fake.asked_for == "sam"
    assert response.json()["username"] == "sam"


def test_crowd_counts_split_the_rest_of_the_league_by_side():
    from src.components.results.results_service import crowd_counts

    rows = [
        # Game 1: sam takes team 10; two others agree, one disagrees.
        {"id": 1, "username": "sam", "game_id": 1, "selected_team_id": 10},
        {"id": 2, "username": "kim", "game_id": 1, "selected_team_id": 10},
        {"id": 3, "username": "lee", "game_id": 1, "selected_team_id": 10},
        {"id": 4, "username": "max", "game_id": 1, "selected_team_id": 11},
        # Game 2: sam is the only one to pick it.
        {"id": 5, "username": "sam", "game_id": 2, "selected_team_id": 20},
        # Game 3: nobody else's business.
        {"id": 6, "username": "kim", "game_id": 3, "selected_team_id": 30},
    ]

    assert crowd_counts(rows, "sam") == {1: (2, 1), 5: (0, 0)}
