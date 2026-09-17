from collections import Counter, defaultdict
from statistics import mean, median

from src.components.results.results_models import TeamDto
from src.components.results.results_stats_models import (
    ConfidenceBreakdownDto,
    GameAwardDto,
    GameBreakdownDto,
    NotablePickDto,
    PickAwardDto,
    PlayerAwardDto,
    PlayerScoreDto,
    SideAwardDto,
    SideBreakdownDto,
    WeekAwardsDto,
    WeekStatsDto,
)
from src.components.results.results_service import ResultsService
from src.components.week.week_service import WeekService
from src.config.base_service import BaseService
from src.util.injection import dependency, inject

# Statuses that represent a decided pick. A push is a refund, not a miss, so it
# is excluded from hit rates rather than counted against them.
GRADED_STATUSES = ("COVERED", "FAILED")

# A side under half of a game's picks is the contrarian one -- but only once
# enough people took the game for "contrarian" to mean anything. One of three is
# arithmetically a minority and socially nothing.
MINORITY_SHARE = 0.5
MIN_PICKS_FOR_MINORITY = 4

# Everyone submits five picks at 5-4-3-2-1, so a perfect week is all five of
# them covering. A push is a refund, not a hit, and doesn't qualify.
PERFECT_WEEK_PICKS = 5


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
            unanimous_picks=[
                _notable(side)
                for game in games
                if game.is_unanimous
                for side in (game.home, game.away)
                if side.pick_count
            ],
            confidence_breakdown=self._confidence_breakdown(picks),
            games=games,
            awards=self._awards(picks, games, scores),
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

    # ------------------------------------------------------------------ awards

    def _awards(
        self,
        picks: list[dict],
        games: list[GameBreakdownDto],
        scores: list[PlayerScoreDto],
    ) -> WeekAwardsDto:
        """
        The week's stories. Every one of these is optional: an award with no
        real winner is left out rather than handed to whoever came closest.
        """
        by_game = {game.game_id: game for game in games}

        # Confidence backing each side, which pick counts alone can't show: the
        # side eight people took at 1 point is not the side eight people took
        # at 5. Built from the raw picks rather than average x count so it
        # doesn't inherit the average's rounding.
        weight: dict[tuple[int, int], float] = defaultdict(float)
        for pick in picks:
            weight[(pick["game_id"], pick["selected_team_id"])] += float(
                pick["confidence"]
            )

        sides = [(game, side) for game in games for side in (game.home, game.away)]

        return WeekAwardsDto(
            player_of_the_week=self._best_scorers(scores),
            perfect_week=self._perfect_week(scores),
            ice_cold=self._worst_scorers(scores),
            value_hunter=self._top_by_pick(
                picks,
                by_game,
                lambda pick, side: (
                    float(pick["score"])
                    if self._is_minority(by_game[pick["game_id"]], side)
                    else 0.0
                ),
            ),
            dog_lover=self._top_by_pick(
                picks,
                by_game,
                lambda pick, side: (
                    float(pick["score"]) if float(pick["spread_value"]) > 0 else 0.0
                ),
            ),
            oracle=self._oracle(picks, by_game, weight),
            **self._consensus_awards(sides, weight),
            sleeper=self._sleeper(sides, weight),
            split_decision=self._split_decision(games),
            **self._margin_awards(sides, weight),
        )

    @classmethod
    def _margin_awards(cls, sides, weight) -> dict:
        """
        The widest cover and the narrowest one. In a week with a single cover
        they are the same side, and one card saying it twice is worse than one
        card saying it once -- so the photo finish stands down.
        """
        covers = [(game, side) for game, side in sides if side.margin > 0]
        if not covers:
            return {"biggest_cover": None, "photo_finish": None}

        widest = cls._side_award(*max(covers, key=lambda p: p[1].margin), weight)
        narrowest = cls._side_award(*min(covers, key=lambda p: p[1].margin), weight)

        same = (
            widest.game_id == narrowest.game_id
            and widest.team.team_id == narrowest.team.team_id
        )
        return {
            "biggest_cover": widest,
            "photo_finish": None if same else narrowest,
        }

    @staticmethod
    def _is_minority(game: GameBreakdownDto, side: SideBreakdownDto) -> bool:
        return (
            game.pick_count >= MIN_PICKS_FOR_MINORITY
            and side.pick_share < MINORITY_SHARE
        )

    @staticmethod
    def _side_of(game: GameBreakdownDto, pick: dict) -> SideBreakdownDto | None:
        if pick["selected_team_id"] == game.home.team.team_id:
            return game.home
        if pick["selected_team_id"] == game.away.team.team_id:
            return game.away
        return None

    @staticmethod
    def _player_award(players: list[PlayerScoreDto], value: float) -> PlayerAwardDto:
        """Several winners share one card rather than one being picked at
        random -- ties are common with five picks each."""
        return PlayerAwardDto(
            usernames=[player.username for player in players],
            value=round(value, 2),
            covered_count=players[0].covered_count if len(players) == 1 else 0,
            failed_count=players[0].failed_count if len(players) == 1 else 0,
            pushed_count=players[0].pushed_count if len(players) == 1 else 0,
        )

    @classmethod
    def _best_scorers(cls, scores: list[PlayerScoreDto]) -> PlayerAwardDto | None:
        if not scores:
            return None
        best = max(player.score for player in scores)
        return cls._player_award(
            [player for player in scores if player.score == best], best
        )

    @classmethod
    def _worst_scorers(cls, scores: list[PlayerScoreDto]) -> PlayerAwardDto | None:
        # With one player, or with everyone level, there is no wooden spoon.
        if len(scores) < 2:
            return None
        worst = min(player.score for player in scores)
        if worst == max(player.score for player in scores):
            return None
        return cls._player_award(
            [player for player in scores if player.score == worst], worst
        )

    @classmethod
    def _perfect_week(cls, scores: list[PlayerScoreDto]) -> PlayerAwardDto | None:
        perfect = [
            player
            for player in scores
            if player.failed_count == 0
            and player.pushed_count == 0
            and player.covered_count >= PERFECT_WEEK_PICKS
        ]
        return cls._player_award(perfect, perfect[0].score) if perfect else None

    @classmethod
    def _top_by_pick(
        cls,
        picks: list[dict],
        by_game: dict[int, GameBreakdownDto],
        points_for,
    ) -> PlayerAwardDto | None:
        """Most points earned from the picks `points_for` cares about. Nobody
        wins if nobody scored any."""
        totals: dict[str, float] = defaultdict(float)
        for pick in picks:
            game = by_game.get(pick["game_id"])
            side = cls._side_of(game, pick) if game else None
            if side:
                totals[pick["username"]] += points_for(pick, side)

        best = max(totals.values(), default=0.0)
        if best <= 0:
            return None
        return PlayerAwardDto(
            usernames=sorted(
                username for username, total in totals.items() if total == best
            ),
            value=round(best, 2),
        )

    @classmethod
    def _oracle(
        cls,
        picks: list[dict],
        by_game: dict[int, GameBreakdownDto],
        weight: dict[tuple[int, int], float],
    ) -> PickAwardDto | None:
        """The boldest contrarian call that came in: highest confidence first,
        and among equals the one fewest people agreed with."""
        best = None
        for pick in picks:
            if pick["pick_status"] != "COVERED":
                continue
            game = by_game.get(pick["game_id"])
            side = cls._side_of(game, pick) if game else None
            if not side or not cls._is_minority(game, side):
                continue
            rank = (pick["confidence"], -side.pick_share)
            if best is None or rank > best[0]:
                best = (rank, pick, game, side)

        if best is None:
            return None

        _, pick, game, side = best
        return PickAwardDto(
            username=pick["username"],
            game_id=game.game_id,
            team=side.team,
            opponent=side.opponent,
            line=side.line,
            confidence=pick["confidence"],
            result=side.result,
            points=float(pick["score"]),
            pick_count=side.pick_count,
            game_pick_count=game.pick_count,
            pick_share=side.pick_share,
        )

    @staticmethod
    def _side_award(
        game: GameBreakdownDto,
        side: SideBreakdownDto,
        weight: dict[tuple[int, int], float],
    ) -> SideAwardDto:
        return SideAwardDto(
            game_id=game.game_id,
            team=side.team,
            opponent=side.opponent,
            line=side.line,
            result=side.result,
            margin=side.margin,
            pick_count=side.pick_count,
            game_pick_count=game.pick_count,
            pick_share=side.pick_share,
            confidence_total=weight.get((game.game_id, side.team.team_id), 0.0),
        )

    @classmethod
    def _consensus_awards(cls, sides, weight) -> dict:
        """
        Where the league put its weight, and whether that was a mistake.

        When the most-backed side lost, those are the same story and one card
        tells it; a second card only appears when the heaviest side came in and
        some other side took the money down with it.
        """
        backed = [(game, side) for game, side in sides if side.pick_count]
        if not backed:
            return {"most_confident": None, "consensus_miss": None}

        def confidence(pair):
            game, side = pair
            return weight.get((game.game_id, side.team.team_id), 0.0)

        top = max(backed, key=confidence)
        most_confident = cls._side_award(*top, weight)

        if most_confident.result != "COVERED":
            return {"most_confident": most_confident, "consensus_miss": None}

        missed = [pair for pair in backed if pair[1].result == "FAILED"]
        if not missed:
            return {"most_confident": most_confident, "consensus_miss": None}

        return {
            "most_confident": most_confident,
            "consensus_miss": cls._side_award(*max(missed, key=confidence), weight),
        }

    @classmethod
    def _sleeper(cls, sides, weight) -> SideAwardDto | None:
        """The side that came in with the league looking the other way."""
        overlooked = [
            (game, side)
            for game, side in sides
            if side.pick_count
            and side.result == "COVERED"
            and cls._is_minority(game, side)
        ]
        if not overlooked:
            return None
        return cls._side_award(
            *min(overlooked, key=lambda pair: pair[1].pick_share), weight
        )

    @staticmethod
    def _split_decision(games: list[GameBreakdownDto]) -> GameAwardDto | None:
        """The game the league could not agree on. Needs two people to disagree
        in the first place."""
        contested = [game for game in games if game.pick_count >= 2]
        if not contested:
            return None

        game = min(
            contested,
            key=lambda g: (
                abs(g.away.pick_count - g.home.pick_count),
                -g.pick_count,
            ),
        )
        return GameAwardDto(
            game_id=game.game_id,
            home_team=game.home_team,
            away_team=game.away_team,
            home_pick_count=game.home.pick_count,
            away_pick_count=game.away.pick_count,
        )

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
