"""
One team's page for one season: its games from its side of the line, and how
the league has played it.

Pure -- rows in, DTO out -- like the season team stats it builds on, and graded
the same way (`side_line`), so a game here always agrees with the team's square
in the standings' team panel.
"""

from collections import defaultdict

from src.components.results.results_math import margin, outcome, team_dto
from src.components.standings.standings_models import (
    TeamGameDto,
    TeamGamePickDto,
    TeamPageDto,
)
from src.components.standings.team_season_stats import (
    GRADES,
    build_team_season_stats,
    side_line,
)

SIDES = (("home_team", "away_team"), ("away_team", "home_team"))


def _sides_of(game: dict, team_id: int) -> tuple[str, str] | None:
    """(the team's prefix, its opponent's), or None if it didn't play in it."""
    for prefix, other in SIDES:
        if game[f"{prefix}_id"] == team_id:
            return prefix, other
    return None


def _pick(row: dict) -> TeamGamePickDto:
    return TeamGamePickDto(
        username=row["username"],
        confidence=int(row["confidence"] or 0),
        pick_status=row["pick_status"],
        score=float(row["score"] or 0.0),
    )


def _by_pick(rows: list[dict]) -> list[TeamGamePickDto]:
    # Highest pick value first, then by name, so the order never shuffles.
    return [
        _pick(row)
        for row in sorted(rows, key=lambda r: (-int(r["confidence"] or 0), r["username"]))
    ]


def _team_games(team_id: int, rows: list[dict], games: list[dict]) -> list[TeamGameDto]:
    by_game: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row["pick_status"] in GRADES:
            by_game[row["game_id"]].append(row)

    out = []
    for game in sorted(games, key=lambda g: g["week_number"]):
        sides = _sides_of(game, team_id)
        if sides is None:
            continue
        prefix, other = sides
        game_rows = by_game.get(game["game_id"], [])
        line = side_line(game, game_rows, prefix, other)
        team_score = game["home_team_score" if prefix == "home_team" else "away_team_score"]
        opponent_score = game["away_team_score" if prefix == "home_team" else "home_team_score"]
        final = team_score is not None and opponent_score is not None
        edge = margin(team_score, line, opponent_score) if final and line is not None else None

        out.append(
            TeamGameDto(
                week=game["week_number"],
                game_id=game["game_id"],
                opponent=team_dto(game, other),
                is_home=prefix == "home_team",
                start_date=game.get("start_date"),
                start_time=game.get("start_time"),
                line=line,
                team_score=team_score,
                opponent_score=opponent_score,
                margin=edge,
                result=outcome(edge) if edge is not None else None,
                picks_for=_by_pick(
                    [r for r in game_rows if r["selected_team_id"] == team_id]
                ),
                picks_against=_by_pick(
                    [r for r in game_rows if r["selected_team_id"] != team_id]
                ),
            )
        )
    return out


def build_team_page(
    team_id: int,
    year: int,
    through_week: int,
    rows: list[dict],
    games: list[dict],
    schedule: list[dict] | None = None,
) -> TeamPageDto | None:
    """
    :param rows: the league's graded picks for `year` through `through_week`.
    :param games: every game of `year` through `through_week`, picked or not.
    :param schedule: the whole season's games, so the page can show the weeks
        still to come. Defaults to `games`.
    :returns: None when the team has no game on record in `year`.
    """
    schedule = games if schedule is None else schedule
    team_games = _team_games(team_id, rows, schedule)
    if not team_games:
        return None

    first = next(g for g in schedule if _sides_of(g, team_id))
    team = team_dto(first, _sides_of(first, team_id)[0])

    stats = build_team_season_stats(rows, year=year, through_week=through_week, games=games)
    season = next((t for t in stats.teams if t.team.team_id == team_id), None)

    return TeamPageDto(
        team=team,
        year=year,
        through_week=through_week,
        season=season,
        games=team_games,
    )
