"""
The season so far, team by team.

Built from the same graded rows the standings table sums by player, grouped by
the team picked instead. Pure -- rows in, DTO out -- so it can be tested without
a database and so the standings service stays a thin caller.
"""

from collections import Counter, defaultdict

from src.components.results.results_math import (
    average,
    margin,
    modal_line,
    outcome,
    rate,
    team_dto,
)
from src.components.standings.standings_models import (
    TeamAwardDto,
    TeamBackerDto,
    TeamSeasonAwardsDto,
    TeamSeasonDto,
    TeamSeasonStatsDto,
    TeamWeekDto,
)

GRADES = ("COVERED", "FAILED", "PUSHED")

# A cover rate over fewer decided picks than this is an anecdote, not a
# record -- one lucky pick would otherwise be a "100%" sure thing.
MIN_DECIDED_FOR_RATE = 5

# Likewise for how fading a team has gone.
MIN_DECIDED_FADES = 3


def _new_team(row: dict, prefix: str) -> dict:
    return {
        "team": team_dto(row, prefix),
        "picks": 0,
        "statuses": Counter(),
        "points_won": 0.0,
        "points_riding": 0,
        "points_missed": 0,
        "confidences": [],
        "players": set(),
        "backers": {},
        "week_picks": Counter(),
        "against": Counter(),
        "form": {},
        "weeks_played": set(),
    }


def _sides(row: dict) -> tuple[str, str] | None:
    """(picked prefix, opponent prefix), or None for a pick on neither team."""
    if row["selected_team_id"] == row["home_team_id"]:
        return "home_team", "away_team"
    if row["selected_team_id"] == row["away_team_id"]:
        return "away_team", "home_team"
    return None


def _decided(statuses: Counter) -> int:
    return statuses["COVERED"] + statuses["FAILED"]


def _book_line(game: dict, prefix: str) -> float | None:
    line = game.get(f"{prefix}_line")
    return None if line is None else float(line)


def _game_form(game: dict, rows: list[dict]) -> dict[int, str]:
    """
    Each side's own result against the spread in one game, keyed by team id.

    A game the league picked is graded at the line it was most commonly picked
    at, the same way the week statistics grade a side, so a square agrees with
    the picks under it. A side nobody took still has a line: it is the other
    side's, negated. A game nobody picked falls back to the house line. One
    that isn't final, or has no line anywhere, has no result.
    """
    if game["home_team_score"] is None or game["away_team_score"] is None:
        return {}

    results = {}
    for prefix, other in (("home_team", "away_team"), ("away_team", "home_team")):
        own = [r for r in rows if r["selected_team_id"] == game[f"{prefix}_id"]]
        theirs = [r for r in rows if r["selected_team_id"] == game[f"{other}_id"]]
        line = modal_line(own)
        if line is None and (opposite := modal_line(theirs)) is not None:
            line = -opposite
        if line is None:
            line = _book_line(game, prefix)
        if line is None and (opposite := _book_line(game, other)) is not None:
            line = -opposite
        if line is None:
            continue
        results[game[f"{prefix}_id"]] = outcome(
            margin(game[f"{prefix}_score"], line, game[f"{other}_score"])
        )
    return results


def _award(entry: dict, value: float, statuses: Counter | None = None) -> TeamAwardDto:
    statuses = entry["statuses"] if statuses is None else statuses
    return TeamAwardDto(
        team=entry["team"],
        value=value,
        pick_count=entry["picks"],
        covered_count=statuses["COVERED"],
        failed_count=statuses["FAILED"],
        pushed_count=statuses["PUSHED"],
    )


def _name(entry: dict) -> str:
    return entry["team"].team_name or ""


def _awards(picked: list[dict]) -> TeamSeasonAwardsDto:
    awards = TeamSeasonAwardsDto()
    if not picked:
        return awards

    # Ties break on the larger sample, then alphabetically, so the same data
    # always names the same team.
    earners = [e for e in picked if e["points_won"] > 0]
    if earners:
        best = max(earners, key=lambda e: (e["points_won"], e["picks"], _name(e)))
        awards.money_team = _award(best, best["points_won"])

    losers = [e for e in picked if e["points_missed"] > 0]
    if losers:
        worst = max(losers, key=lambda e: (e["points_missed"], e["picks"], _name(e)))
        awards.money_pit = _award(worst, worst["points_missed"])

    most = max(picked, key=lambda e: (e["picks"], e["points_won"], _name(e)))
    awards.most_picked = _award(most, most["picks"])

    rated = [
        (rate(e["statuses"]["COVERED"], _decided(e["statuses"])), e)
        for e in picked
        if _decided(e["statuses"]) >= MIN_DECIDED_FOR_RATE
    ]
    # "Sure thing" and "least trusted" only mean something on the right side
    # of a coin flip.
    above = [(r, e) for r, e in rated if r > 0.5]
    if above:
        r, e = max(above, key=lambda p: (p[0], _decided(p[1]["statuses"]), _name(p[1])))
        awards.sure_thing = _award(e, r)
    below = [(r, e) for r, e in rated if r < 0.5]
    if below:
        r, e = min(
            below, key=lambda p: (p[0], -_decided(p[1]["statuses"]), _name(p[1]))
        )
        awards.least_trusted = _award(e, r)

    return awards


def _underrated(entries: list[dict]) -> TeamAwardDto | None:
    """The team the league was most often wrong to pick against."""
    faded = [
        (rate(e["against"]["COVERED"], _decided(e["against"])), e)
        for e in entries
        if _decided(e["against"]) >= MIN_DECIDED_FADES
    ]
    wrong = [(r, e) for r, e in faded if r < 0.5]
    if not wrong:
        return None
    r, e = max(
        wrong,
        key=lambda p: (p[1]["against"]["FAILED"], -p[0], _name(p[1])),
    )
    award = _award(e, r, statuses=e["against"])
    award.pick_count = sum(e["against"].values())
    return award


def build_team_season_stats(
    rows: list[dict], year: int, through_week: int, games: list[dict] = ()
) -> TeamSeasonStatsDto:
    """
    :param rows: the league's graded picks through `through_week`.
    :param games: every game of the season through `through_week`, picked or
        not, with each side's house line -- what grades the weeks nobody picked
        and tells a bye from a game.
    """
    teams: dict[int, dict] = {}
    by_game: dict[int, list[dict]] = defaultdict(list)
    totals = Counter()
    points_won = 0.0
    points_riding = 0

    for row in rows:
        sides = _sides(row)
        if sides is None or row["pick_status"] not in GRADES:
            continue
        picked, opponent = sides
        for prefix in sides:
            team_id = row[f"{prefix}_id"]
            if team_id not in teams:
                teams[team_id] = _new_team(row, prefix)

        by_game[row["game_id"]].append(row)

        status = row["pick_status"]
        confidence = int(row["confidence"] or 0)
        score = float(row["score"] or 0.0)

        entry = teams[row[f"{picked}_id"]]
        entry["picks"] += 1
        entry["statuses"][status] += 1
        entry["points_won"] += score
        entry["points_riding"] += confidence
        if status == "FAILED":
            entry["points_missed"] += confidence
        entry["confidences"].append(confidence)
        entry["players"].add(row["username"])
        entry["week_picks"][row["week_number"]] += 1

        backer = entry["backers"].setdefault(
            row["username"], {"picks": 0, "statuses": Counter(), "points_won": 0.0}
        )
        backer["picks"] += 1
        backer["statuses"][status] += 1
        backer["points_won"] += score

        teams[row[f"{opponent}_id"]]["against"][status] += 1

        totals[status] += 1
        points_won += score
        points_riding += confidence

    # Every game of the season, picked or not. Without the schedule, only the
    # picked games are known, and a team's other weeks can't be told from byes.
    schedule = {game["game_id"]: game for game in games}
    for game in games:
        for prefix in ("home_team", "away_team"):
            team_id = game[f"{prefix}_id"]
            if team_id not in teams:
                teams[team_id] = _new_team(game, prefix)
            teams[team_id]["weeks_played"].add(game["week_number"])
    for game_id, game_rows in by_game.items():
        schedule.setdefault(game_id, game_rows[0])

    for game_id, game in schedule.items():
        week = game["week_number"]
        for team_id, result in _game_form(game, by_game.get(game_id, [])).items():
            teams[team_id]["form"][week] = result

    entries = list(teams.values())
    picked = [e for e in entries if e["picks"]]

    def to_dto(e: dict) -> TeamSeasonDto:
        return TeamSeasonDto(
            team=e["team"],
            pick_count=e["picks"],
            player_count=len(e["players"]),
            covered_count=e["statuses"]["COVERED"],
            failed_count=e["statuses"]["FAILED"],
            pushed_count=e["statuses"]["PUSHED"],
            hit_rate=rate(e["statuses"]["COVERED"], _decided(e["statuses"])),
            points_won=round(e["points_won"], 2),
            points_riding=e["points_riding"],
            points_missed=e["points_missed"],
            average_confidence=average(e["confidences"]),
            against_count=sum(e["against"].values()),
            against_covered_count=e["against"]["COVERED"],
            against_failed_count=e["against"]["FAILED"],
            against_pushed_count=e["against"]["PUSHED"],
            form=[
                TeamWeekDto(
                    week=week,
                    result=e["form"].get(week),
                    pick_count=e["week_picks"].get(week, 0),
                    bye=bool(games) and week not in e["weeks_played"],
                )
                for week in range(1, through_week + 1)
            ],
            backers=[
                TeamBackerDto(
                    username=username,
                    pick_count=b["picks"],
                    covered_count=b["statuses"]["COVERED"],
                    failed_count=b["statuses"]["FAILED"],
                    pushed_count=b["statuses"]["PUSHED"],
                    points_won=round(b["points_won"], 2),
                )
                for username, b in sorted(
                    e["backers"].items(),
                    key=lambda item: (
                        -item[1]["picks"],
                        -item[1]["points_won"],
                        item[0],
                    ),
                )
            ],
        )

    awards = _awards(picked)
    awards.underrated = _underrated(entries)

    return TeamSeasonStatsDto(
        year=year,
        through_week=through_week,
        pick_count=sum(totals.values()),
        covered_count=totals["COVERED"],
        failed_count=totals["FAILED"],
        pushed_count=totals["PUSHED"],
        hit_rate=rate(totals["COVERED"], totals["COVERED"] + totals["FAILED"]),
        points_won=round(points_won, 2),
        points_riding=points_riding,
        # Most points won first -- the order the page opens in.
        teams=[
            to_dto(e)
            for e in sorted(
                picked, key=lambda e: (-e["points_won"], -e["picks"], _name(e))
            )
        ],
        never_picked=[e["team"] for e in sorted(entries, key=_name) if not e["picks"]],
        awards=awards,
    )
