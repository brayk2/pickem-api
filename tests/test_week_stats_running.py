import asyncio

from src.components.results.results_stats_service import ResultsStatsService

TEAMS = {1: "Chiefs", 2: "Raiders"}


def _team(prefix: str, team_id: int) -> dict:
    return {
        f"{prefix}_id": team_id,
        f"{prefix}_name": TEAMS[team_id],
        f"{prefix}_city": "City",
        f"{prefix}_abbreviation": None,
        f"{prefix}_thumbnail": None,
        f"{prefix}_primary_color": None,
        f"{prefix}_secondary_color": None,
    }


def pick(username, selected, line, confidence, status):
    """One graded row for KC (home, -3) beating LV 24-17: KC covers by 4."""
    score = {"COVERED": confidence, "PUSHED": confidence / 2}.get(status, 0.0)
    return {
        "username": username,
        "week_number": 3,
        "game_id": 10,
        "spread_value": line,
        "confidence": confidence,
        "score": score,
        "pick_status": status,
        "home_team_score": 24,
        "away_team_score": 17,
        **_team("home_team", 1),
        **_team("away_team", 2),
        **_team("selected_team", selected),
    }


ROWS = [
    pick("ann", 1, -3, 5, "COVERED"),
    pick("bob", 1, -3, 3, "COVERED"),
    pick("cat", 2, 3, 2, "FAILED"),
]


def _stats(rows, complete):
    service = ResultsStatsService(mock=True)
    service.week_service.is_complete.return_value = complete
    service.results_service.get_graded_picks_for_week.return_value = rows
    return asyncio.run(service.get_week_stats(year=2026, week=3, league_id=1))


def test_in_progress_week_has_running_stats_but_no_awards():
    stats = _stats(ROWS, complete=False)

    assert stats.completed is False
    assert stats.pick_count == 3
    assert stats.game_count == 1
    assert abs(stats.hit_rate - 2 / 3) < 0.001
    assert [c.confidence for c in stats.confidence_breakdown]
    assert stats.awards.model_dump(exclude_none=True) == {}


def test_complete_week_gets_awards():
    stats = _stats(ROWS, complete=True)

    assert stats.completed is True
    assert stats.pick_count == 3
    assert stats.awards.player_of_the_week is not None


def test_week_with_nothing_graded_is_empty_either_way():
    for complete in (False, True):
        stats = _stats([], complete=complete)
        assert stats.completed is complete
        assert stats.pick_count == 0
        assert stats.games == []
