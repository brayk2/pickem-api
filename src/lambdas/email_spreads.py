import asyncio
from itertools import groupby

from src.components.email.email_models import EmailMessage
from src.components.email.email_service import EmailService
from src.integrations.queue_service import QueueService
from src.components.results.results_models import MatchupDto, TeamDto
from src.components.season.season_service import SeasonService
from src.models.db_models import (
    LeagueMemberModel,
    LeagueSeasonModel,
    SeasonModel,
    UserModel,
)
from src.components.spread.spread_service import SpreadService


def _format_line(line: str | None) -> str | None:
    if line is None:
        return None
    value = float(line)
    if value == 0:
        return "PK"
    return line if value < 0 else f"+{line}"


def _side(team: TeamDto, lines: dict) -> dict:
    line = lines.get(team.team_name)
    return {
        "name": f"{team.team_city} {team.team_name}",
        "line": _format_line(line),
        "favorite": line is not None and float(line) < 0,
    }


def _days(matchups: list[MatchupDto]) -> list[dict]:
    """Games grouped under a heading per kickoff day, in kickoff order."""
    ordered = sorted(
        matchups,
        key=lambda m: (
            m.start_date is None,
            m.start_date,
            m.start_time is None,
            m.start_time,
        ),
    )
    return [
        {
            "label": day.strftime("%A, %B %-d") if day else "Date TBD",
            "games": [
                {
                    "away": _side(m.away_team, m.lines or {}),
                    "home": _side(m.home_team, m.lines or {}),
                }
                for m in games
            ],
        }
        for day, games in groupby(ordered, key=lambda m: m.start_date)
    ]


def _enrolled_users(year: int):
    """Users on any league's roster for the season. Distinct, because one
    user can play in more than one league in the same year."""
    return (
        UserModel.select()
        .join(LeagueMemberModel, on=(LeagueMemberModel.user == UserModel.id))
        .join(
            LeagueSeasonModel,
            on=(LeagueMemberModel.league_season == LeagueSeasonModel.id),
        )
        .join(SeasonModel, on=(LeagueSeasonModel.season == SeasonModel.id))
        .where(SeasonModel.year == year)
        .distinct()
    )


async def read_and_notify():
    spread_service = SpreadService()
    season_service = SeasonService()
    week_info = season_service.get_current_week_and_year()
    year, week = week_info.get("year"), week_info.get("week")

    matchups = await spread_service.get_matchup_data(
        year=year, week=week, bookmaker="DraftKings"
    )

    subject = f"Pickem Lines | Week {week}"

    # Same email for everyone, so render it once. render_template is static:
    # no EmailService instance, so no SMTP credentials fetched here -- the
    # send_email lambda does the sending.
    message_parts = EmailService.render_template(
        "weekly_lines",
        year=year,
        week=week,
        days=_days(matchups),
        picks_url=f"https://pickem-webapp.vercel.app/picks/{year}/{week}",
    )

    queue_service = QueueService()
    messages = []
    for user in _enrolled_users(year):
        try:
            queue_service.send_email(
                EmailMessage(
                    recipient=user.email,
                    subject=subject,
                    message_parts=message_parts,
                )
            )
            messages.append(
                {
                    "message": f"Queued lines for {user.email}",
                    "status": "queued",
                }
            )
        except Exception:
            messages.append(
                {
                    "message": f"failed to queue email to {user.email}",
                    "status": "failed",
                }
            )
    return messages


def handle_event(event, context):
    return asyncio.run(read_and_notify())


if __name__ == "__main__":
    handle_event({}, {})
