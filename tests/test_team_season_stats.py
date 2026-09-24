from src.components.standings.team_season_stats import build_team_season_stats

TEAMS = {
    1: "Chiefs",
    2: "Raiders",
    3: "Bills",
    4: "Jets",
}


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


def pick(
    username,
    week,
    game_id,
    home,
    away,
    home_score,
    away_score,
    selected,
    line,
    confidence,
    status,
):
    """One graded row, shaped like ResultsService's graded-picks query."""
    score = {"COVERED": confidence, "PUSHED": confidence / 2}.get(status, 0.0)
    return {
        "username": username,
        "week_number": week,
        "game_id": game_id,
        "spread_value": line,
        "confidence": confidence,
        "score": score,
        "pick_status": status,
        "home_team_score": home_score,
        "away_team_score": away_score,
        **_team("home_team", home),
        **_team("away_team", away),
        **_team("selected_team", selected),
    }


# Week 1: KC (home, -3) beats LV 24-17 -> KC covers by 4.
# Week 2: BUF (home, -7) beats NYJ 20-17 -> BUF misses by 4; NYJ covers.
ROWS = [
    pick("ann", 1, 10, 1, 2, 24, 17, 1, -3, 5, "COVERED"),
    pick("bob", 1, 10, 1, 2, 24, 17, 1, -3, 3, "COVERED"),
    pick("cat", 1, 10, 1, 2, 24, 17, 2, 3, 2, "FAILED"),
    pick("ann", 2, 11, 3, 4, 20, 17, 3, -7, 4, "FAILED"),
    pick("bob", 2, 11, 3, 4, 20, 17, 3, -7, 5, "FAILED"),
]


def stats():
    return build_team_season_stats(ROWS, year=2025, through_week=2)


def team(result, name):
    return next(t for t in result.teams if t.team.team_name == name)


def test_league_totals():
    s = stats()
    assert (s.pick_count, s.covered_count, s.failed_count) == (5, 2, 3)
    assert s.hit_rate == 0.4
    assert s.points_won == 8.0
    assert s.points_riding == 19


def test_team_record_and_points():
    kc = team(stats(), "Chiefs")
    assert (kc.pick_count, kc.player_count) == (2, 2)
    assert (kc.covered_count, kc.failed_count) == (2, 0)
    assert kc.points_won == 8.0
    assert kc.points_missed == 0
    assert kc.average_confidence == 4.0

    bills = team(stats(), "Bills")
    assert bills.points_missed == 9
    assert bills.hit_rate == 0.0


def test_picks_against_are_graded_from_the_pickers_side():
    kc = team(stats(), "Chiefs")
    # cat took LV against KC and missed.
    assert (kc.against_count, kc.against_failed_count) == (1, 1)


def test_form_grades_each_team_including_ones_nobody_took():
    s = stats()
    kc = team(s, "Chiefs")
    assert [(w.week, w.result, w.pick_count) for w in kc.form] == [
        (1, "COVERED", 2),
        (2, None, 0),
    ]
    # Nobody picked the Jets, but their game had picks, so they still have a
    # graded week: +7 at 17-20 covers.
    assert [n.team_name for n in s.never_picked] == ["Jets"]


def test_teams_open_sorted_by_points_won_then_picks():
    # Bills and Raiders both scored nothing; the more-picked team leads.
    assert [t.team.team_name for t in stats().teams] == ["Chiefs", "Bills", "Raiders"]


def test_backers_most_picks_first():
    kc = team(stats(), "Chiefs")
    assert [(b.username, b.points_won) for b in kc.backers] == [
        ("ann", 5.0),
        ("bob", 3.0),
    ]


def test_awards():
    awards = stats().awards
    assert awards.money_team.team.team_name == "Chiefs"
    assert awards.money_team.value == 8.0
    assert awards.money_pit.team.team_name == "Bills"
    assert awards.money_pit.value == 9
    # Nothing has enough decided picks for a rate award yet.
    assert awards.sure_thing is None
    assert awards.least_trusted is None


def test_rate_awards_need_a_real_sample():
    rows = [
        pick(f"p{i}", 1, 20 + i, 1, 2, 24, 17, 1, -3, 1, "COVERED") for i in range(5)
    ] + [pick(f"q{i}", 1, 30 + i, 3, 4, 10, 20, 3, -3, 1, "FAILED") for i in range(5)]
    awards = build_team_season_stats(rows, year=2025, through_week=1).awards
    assert awards.sure_thing.team.team_name == "Chiefs"
    assert awards.sure_thing.value == 1.0
    assert awards.least_trusted.team.team_name == "Bills"


def test_underrated_is_the_team_fading_went_worst_on():
    rows = [pick(f"p{i}", 1, 40 + i, 1, 2, 30, 10, 2, 3, 2, "FAILED") for i in range(3)]
    award = build_team_season_stats(rows, year=2025, through_week=1).awards.underrated
    assert award.team.team_name == "Chiefs"
    assert (award.pick_count, award.failed_count) == (3, 3)


def test_skips_picks_on_neither_team():
    bad = pick("zed", 1, 10, 1, 2, 24, 17, 3, -3, 5, "UNKNOWN")
    s = build_team_season_stats([bad], year=2025, through_week=1)
    assert s.pick_count == 0 and s.teams == []


def test_empty_season():
    s = build_team_season_stats([], year=2025, through_week=3)
    assert s.teams == [] and s.hit_rate is None
    assert s.awards.money_team is None
