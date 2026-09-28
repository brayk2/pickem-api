from src.components.standings.team_page import build_team_page
from tests.test_team_season_stats import GAMES, ROWS, game, pick

KC, LV, BUF = 1, 2, 3


def page(**kwargs):
    return build_team_page(
        KC, year=2025, through_week=3, rows=ROWS, games=GAMES, **kwargs
    )


def test_team_and_season_come_from_the_same_grading_as_the_team_panel():
    p = page()
    assert p.team.team_name == "Chiefs"
    assert (p.season.pick_count, p.season.covered_count) == (2, 2)


def test_games_are_from_the_teams_side_including_ones_nobody_picked():
    games = page().games
    assert [(g.week, g.opponent.team_name, g.is_home) for g in games] == [
        (1, "Raiders", True),
        (2, "Raiders", False),
    ]

    week1, week2 = games
    # Graded at the line the league took it at: 24 - 3 - 17 = +4.
    assert (week1.line, week1.team_score, week1.opponent_score) == (-3.0, 24, 17)
    assert (week1.margin, week1.result) == (4.0, "COVERED")
    # Nobody picked it: the house line, +1 at 10-30.
    assert (week2.line, week2.margin, week2.result) == (1.0, -19.0, "FAILED")


def test_picks_on_each_side_highest_value_first():
    week1 = page().games[0]
    assert [(p.username, p.confidence) for p in week1.picks_for] == [
        ("ann", 5),
        ("bob", 3),
    ]
    assert [(p.username, p.pick_status) for p in week1.picks_against] == [
        ("cat", "FAILED")
    ]


def test_a_game_not_final_has_no_result():
    unfinished = [game(20, 1, KC, LV, None, None, -3.0, 3.0)]
    (only,) = build_team_page(
        KC, year=2025, through_week=1, rows=[], games=unfinished
    ).games
    assert (only.margin, only.result) == (None, None)


def test_a_team_with_no_games_that_season_has_no_page():
    assert build_team_page(99, year=2025, through_week=3, rows=ROWS, games=GAMES) is None


def test_the_schedule_adds_the_weeks_still_to_come():
    upcoming = game(30, 5, BUF, KC, None, None, 2.5, -2.5)
    p = page(schedule=GAMES + [upcoming])
    assert [g.week for g in p.games] == [1, 2, 5]
    later = p.games[-1]
    assert (later.opponent.team_name, later.is_home) == ("Bills", False)
    assert (later.line, later.result) == (-2.5, None)
    # The season so far is still only the weeks played.
    assert p.season.pick_count == 2
