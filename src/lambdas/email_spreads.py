import asyncio

from src.components.email.email_service import EmailService
from src.components.email.utils import generate_html_table
from src.components.season.season_service import SeasonService
from src.models.new_db_models import UserModel
from src.services.spread_service import SpreadService


async def read_and_notify():
    spread_service = SpreadService()
    season_service = SeasonService()
    week_info = season_service.get_current_week_and_year()

    spreads = await spread_service.get_matchup_data(
        year=week_info.get("year"), week=week_info.get("week"), bookmaker="DraftKings"
    )

    lines = [
        {
            key: str(val) if float(val) < 0 else f"+{val}"
            for key, val in spread.lines.items()
        }
        for spread in spreads
    ]
    table = generate_html_table(data=lines)

    email_service = EmailService()
    subject = f"Pickem Lines | Week {week_info.get('week')}"

    intro = f"Here are the lines for week {week_info.get('week')}:\n\n"
    outro = f"\n\nMake your picks at https://pickem-webapp.vercel.app/picks/{week_info.get('year')}/{week_info.get('week')}"

    # Prepare message parts
    message_parts = [
        {"content": intro, "subtype": "plain"},
        {"content": table, "subtype": "html"},
        {"content": outro, "subtype": "plain"},
    ]

    messages = []
    for user in UserModel.select():
        try:
            # email_service.send_email(
            #     recipient=user.email, subject=subject, message_parts=message_parts
            # )
            messages.append(
                {
                    "message": f"Successfully sent lines to {user.email}",
                    "status": "success",
                }
            )
        except Exception:
            messages.append(
                {"message": f"failed to send email to {user.email}", "status": "failed"}
            )
    return messages


def handle_event(event, context):
    return asyncio.run(read_and_notify())
