from collections import Counter, defaultdict
from statistics import mean, median

from src.components.results.results_dto import TeamDto
from src.components.results.results_stats_dto import (
    ConfidenceBreakdownDto,
    GameBreakdownDto,
    MarginPickDto,
    NotablePickDto,
    PlayerConvictionDto,
    PlayerScoreDto,
    SideBreakdownDto,
    SoloHitDto,
    WeekStatsDto,
    WeekSuperlativesDto,
)
from src.components.results.results_service import ResultsService
from src.components.week.week_service import WeekService
from src.config.base_service import BaseService
from src.util.injection import dependency, inject

# Statuses that represent a decided pick. A push is a refund, not a miss, so it
# is excluded from hit rates rather than counted against them.
GRADED_STATUSES = ("COVERED", "FAILED")

# A pick decided by a field goal or less was a coin flip dressed up as a read.
# Wide enough to catch the hook and the three, narrow enough to stay a story.
PHOTO_FINISH_MARGIN = 3.0
MAX_PHOTO_FINISHES = 4


def _team_dto(row: dict, prefix: str) -> TeamDto:
    return TeamDto(
        team_id=row[f"{prefix}_id"],
        team_name=row[f"{prefix}_name"],
        team_city=row[f"{prefix}_city"],
        abbreviation=row[f"{prefix}_abbreviation"],
        thumbnail=row[f"{prefix}_thumbnail"],
        primary_color=row[f"{prefix}_primary_color"],
        secondary_color=row[f"{prefix}_secondary_color"],
    )


def _rate(numerator: int, denominator: int) -> float | None:
    """None rather than 0.0 when there is nothing to divide by -- a week with no
    decided picks has an unknown hit rate, not a 0% one."""
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def _average(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def _modal_line(rows: list[dict]) -> float | None:
    """
    The line the side was most commonly taken at.

    Picks store the number the player took, so a line that moved mid-week leaves
    a game with two of them. The common value is what the week was played at.
    """
    if not rows:
        return None
    return Counter(float(row["spread_value"]) for row in rows).most_common(1)[0][0]


def _margin(team_score: int, line: float, opponent_score: int) -> float:
    """Points this side beat its line by; negative means it fell short."""
    return round(team_score + line - opponent_score, 2)


def _outcome(margin: float) -> str:
    if margin > 0:
        return "COVERED"
    if margin < 0:
        return "FAILED"
    return "PUSHED"


@dependency
class ResultsStatsService(BaseService):
    """
    Builds the end-of-week statistics panel from the same graded picks the
    leaderboard is built from, grouped by game instead of by player.
    """

    @inject
    def __init__(self, results_service: ResultsService, week_service: WeekService):
        super().__init__()
        self.results_service = results_service
        self.week_service = week_service

    async def get_week_stats(
        self, year: int, week: int, league_id: int
    ) -> WeekStatsDto:
        if not self.week_service.is_complete(year=year, week=week):
            self.logger.info(
                f"Week {week} of {year} is not complete; withholding week stats"
            )
            return WeekStatsDto(year=year, week=week, completed=False)

        picks = self.results_service.get_graded_picks_for_week(
            year=year, week=week, league_id=league_id
        )
        if not picks:
            self.logger.info(f"Week {week} of {year} is complete but has no picks")
            return WeekStatsDto(year=year, week=week, completed=True)

        games = self._build_game_breakdowns(picks)
        sides = [side for game in games for side in (game.home, game.away)]
        picked_sides = [side for side in sides if side.pick_count]

        statuses = Counter(pick["pick_status"] for pick in picks)
        decided = sum(statuses[status] for status in GRADED_STATUSES)
        scores = self._player_scores(picks)

        return WeekStatsDto(
            year=year,
            week=week,
            completed=True,
            player_count=len(scores),
            pick_count=len(picks),
            game_count=len(games),
            average_score=_average([player.score for player in scores]),
            median_score=round(median([player.score for player in scores]), 2),
            hit_rate=_rate(statuses["COVERED"], decided),
            most_popular_pick=self._pick_extreme(picked_sides, "pick_count"),
            most_correct_pick=self._pick_extreme(picked_sides, "covered_count"),
            most_missed_pick=self._pick_extreme(picked_sides, "failed_count"),
            unanimous_picks=[
                _notable(side)
                for game in games
                if game.is_unanimous
                for side in (game.home, game.away)
                if side.pick_count
            ],
            confidence_breakdown=self._confidence_breakdown(picks),
            games=games,
            superlatives=self._superlatives(picks, games, scores),
        )

    def _build_game_breakdowns(self, picks: list[dict]) -> list[GameBreakdownDto]:
        by_game: dict[int, list[dict]] = defaultdict(list)
        for pick in picks:
            by_game[pick["game_id"]].append(pick)

        breakdowns = []
        for game_id, rows in by_game.items():
            first = rows[0]
            home_team = _team_dto(first, "home_team")
            away_team = _team_dto(first, "away_team")
            home_score = first["home_team_score"]
            away_score = first["away_team_score"]

            home_rows = [r for r in rows if r["selected_team_id"] == r["home_team_id"]]
            away_rows = [r for r in rows if r["selected_team_id"] == r["away_team_id"]]

            home_line = _modal_line(home_rows)
            away_line = _modal_line(away_rows)
            if home_line is None and away_line is None:
                # Every pick on this game names a team that is not playing in it.
                self.logger.warning(f"Game {game_id} has picks on neither side")
                continue
            # The two sides of a spread are the same number with opposite signs,
            # so a side nobody took still has a knowable line.
            if home_line is None:
                home_line = -away_line
            if away_line is None:
                away_line = -home_line

            home_margin = _margin(home_score, home_line, away_score)
            away_margin = _margin(away_score, away_line, home_score)

            statuses = Counter(row["pick_status"] for row in rows)
            decided = sum(statuses[status] for status in GRADED_STATUSES)

            breakdowns.append(
                GameBreakdownDto(
                    game_id=game_id,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=home_score,
                    away_score=away_score,
                    home=_side_breakdown(
                        game_id=game_id,
                        team=home_team,
                        opponent=away_team,
                        line=home_line,
                        margin=home_margin,
                        rows=home_rows,
                        game_pick_count=len(rows),
                    ),
                    away=_side_breakdown(
                        game_id=game_id,
                        team=away_team,
                        opponent=home_team,
                        line=away_line,
                        margin=away_margin,
                        rows=away_rows,
                        game_pick_count=len(rows),
                    ),
                    pick_count=len(rows),
                    covered_count=statuses["COVERED"],
                    failed_count=statuses["FAILED"],
                    pushed_count=statuses["PUSHED"],
                    hit_rate=_rate(statuses["COVERED"], decided),
                    average_points=_average([float(row["score"]) for row in rows]),
                    # One player agreeing with themselves is not a consensus.
                    is_unanimous=len(rows) > 1
                    and len(rows) in (len(home_rows), len(away_rows)),
                )
            )

        # Most-picked games first: those are the ones the week turned on.
        return sorted(breakdowns, key=lambda g: (-g.pick_count, g.game_id))

    @staticmethod
    def _player_scores(picks: list[dict]) -> list[PlayerScoreDto]:
        totals: dict[str, float] = defaultdict(float)
        statuses: dict[str, Counter] = defaultdict(Counter)
        for pick in picks:
            totals[pick["username"]] += float(pick["score"])
            statuses[pick["username"]][pick["pick_status"]] += 1

        return sorted(
            (
                PlayerScoreDto(
                    username=username,
                    score=round(score, 2),
                    covered_count=statuses[username]["COVERED"],
                    failed_count=statuses[username]["FAILED"],
                    pushed_count=statuses[username]["PUSHED"],
                )
                for username, score in totals.items()
            ),
            key=lambda player: (-player.score, player.username),
        )

    @staticmethod
    def _pick_extreme(
        sides: list[SideBreakdownDto], field: str
    ) -> NotablePickDto | None:
        """The side with the most of `field`, or None when no side has any."""
        if not sides:
            return None
        best = max(sides, key=lambda side: (getattr(side, field), side.pick_count))
        if not getattr(best, field):
            return None
        return _notable(best)

    @staticmethod
    def _confidence_breakdown(picks: list[dict]) -> list[ConfidenceBreakdownDto]:
        by_confidence: dict[int, list[dict]] = defaultdict(list)
        for pick in picks:
            by_confidence[pick["confidence"]].append(pick)

        breakdown = []
        for confidence in sorted(by_confidence, reverse=True):
            rows = by_confidence[confidence]
            statuses = Counter(row["pick_status"] for row in rows)
            decided = sum(statuses[status] for status in GRADED_STATUSES)
            breakdown.append(
                ConfidenceBreakdownDto(
                    confidence=confidence,
                    pick_count=len(rows),
                    covered_count=statuses["COVERED"],
                    failed_count=statuses["FAILED"],
                    pushed_count=statuses["PUSHED"],
                    hit_rate=_rate(statuses["COVERED"], decided),
                    average_points=_average([float(row["score"]) for row in rows]),
                )
            )
        return breakdown

    @staticmethod
    def _conviction(
        picks: list[dict],
    ) -> tuple[PlayerConvictionDto | None, PlayerConvictionDto | None]:
        """
        Who put their confidence on the picks that came in, and who spent it on
        the ones that didn't.

        Measured as points per correct pick: six points off three correct is a
        2.0, five points off one correct is a 5.0. A player with nothing correct
        has no ratio at all rather than a zero -- they had a bad week, which is
        what `worst_score` is for.
        """
        totals: dict[str, float] = defaultdict(float)
        hits: dict[str, int] = defaultdict(int)
        scores: dict[str, float] = defaultdict(float)
        for pick in picks:
            scores[pick["username"]] += float(pick["score"])
            if pick["pick_status"] == "COVERED":
                totals[pick["username"]] += float(pick["confidence"])
                hits[pick["username"]] += 1

        ranked = sorted(
            (
                PlayerConvictionDto(
                    username=username,
                    score=round(scores[username], 2),
                    covered_count=hits[username],
                    points_per_hit=round(totals[username] / hits[username], 2),
                )
                for username in hits
            ),
            key=lambda player: (-player.points_per_hit, player.username),
        )

        # With fewer than two players on the board there is no comparison to
        # draw, and the best and worst would be the same person. Identical
        # ratios are the same problem one step along: naming a winner and a
        # loser who scored the same thing says nothing about either.
        if len(ranked) < 2 or ranked[0].points_per_hit == ranked[-1].points_per_hit:
            return None, None
        return ranked[0], ranked[-1]

    @staticmethod
    def _photo_finishes(picks: list[dict]) -> list[MarginPickDto]:
        """
        The picks that came down to nothing -- a hook, a late field goal. Both
        directions: missing by half a point is the week's story, and surviving
        by half a point is the same story from the other side.
        """
        close = [
            pick
            for pick in picks
            if pick.get("margin") is not None
            and pick["pick_status"] in GRADED_STATUSES
            and abs(pick["margin"]) <= PHOTO_FINISH_MARGIN
        ]
        # Tightest first, and among equally tight ones the most confident --
        # losing a 5-pointer by a hook stings more than losing a 1-pointer.
        close.sort(key=lambda pick: (abs(pick["margin"]), -pick["confidence"]))

        return [
            MarginPickDto(
                username=pick["username"],
                game_id=pick["game_id"],
                team=_team_dto(pick, "selected_team"),
                opponent=_team_dto(
                    pick,
                    (
                        "away_team"
                        if pick["selected_team_id"] == pick["home_team_id"]
                        else "home_team"
                    ),
                ),
                line=float(pick["spread_value"]),
                confidence=pick["confidence"],
                result=pick["pick_status"],
                margin=pick["margin"],
                points=float(pick["score"]),
            )
            for pick in close[:MAX_PHOTO_FINISHES]
        ]

    @staticmethod
    def _superlatives(
        picks: list[dict],
        games: list[GameBreakdownDto],
        scores: list[PlayerScoreDto],
    ) -> WeekSuperlativesDto:
        # Best and worst are the same player in a one-player league, which is
        # not a superlative worth showing.
        best, worst = (scores[0], scores[-1]) if len(scores) > 1 else (None, None)

        # A side exactly one player took, in a game more than one player picked.
        solo_sides = {
            (game.game_id, side.team.team_id)
            for game in games
            if game.pick_count > 1
            for side in (game.home, game.away)
            if side.pick_count == 1
        }

        solo_hits = [
            SoloHitDto(
                username=pick["username"],
                game_id=pick["game_id"],
                team=_team_dto(pick, "selected_team"),
                opponent=_team_dto(
                    pick,
                    (
                        "away_team"
                        if pick["selected_team_id"] == pick["home_team_id"]
                        else "home_team"
                    ),
                ),
                line=float(pick["spread_value"]),
                confidence=pick["confidence"],
                points=float(pick["score"]),
            )
            for pick in picks
            if pick["pick_status"] == "COVERED"
            and (pick["game_id"], pick["selected_team_id"]) in solo_sides
        ]
        solo_hits.sort(key=lambda hit: (-hit.points, hit.username))

        best_conviction, misplaced_conviction = ResultsStatsService._conviction(picks)

        return WeekSuperlativesDto(
            best_score=best,
            worst_score=worst,
            best_conviction=best_conviction,
            misplaced_conviction=misplaced_conviction,
            solo_hits=solo_hits,
            photo_finishes=ResultsStatsService._photo_finishes(picks),
        )


def _side_breakdown(
    game_id: int,
    team: TeamDto,
    opponent: TeamDto,
    line: float,
    margin: float,
    rows: list[dict],
    game_pick_count: int,
) -> SideBreakdownDto:
    statuses = Counter(row["pick_status"] for row in rows)
    distinct = set(statuses)

    if not rows:
        # Nobody took this side, so grade it from the line the other side implies.
        result = _outcome(margin)
    elif len(distinct) == 1:
        result = distinct.pop()
    else:
        result = "MIXED"

    return SideBreakdownDto(
        game_id=game_id,
        team=team,
        opponent=opponent,
        line=line,
        margin=margin,
        result=result,
        pick_count=len(rows),
        pick_share=round(len(rows) / game_pick_count, 4) if game_pick_count else 0.0,
        covered_count=statuses["COVERED"],
        failed_count=statuses["FAILED"],
        pushed_count=statuses["PUSHED"],
        average_confidence=_average([float(row["confidence"]) for row in rows]),
        average_points=_average([float(row["score"]) for row in rows]),
        total_points=round(sum(float(row["score"]) for row in rows), 2),
    )


def _notable(side: SideBreakdownDto) -> NotablePickDto:
    return NotablePickDto(
        game_id=side.game_id,
        team=side.team,
        opponent=side.opponent,
        line=side.line,
        result=side.result,
        pick_count=side.pick_count,
        pick_share=side.pick_share,
        covered_count=side.covered_count,
        failed_count=side.failed_count,
        average_points=side.average_points,
    )
