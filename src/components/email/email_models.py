from typing import Literal

from pydantic import BaseModel


class EmailPart(BaseModel):
    content: str
    subtype: Literal["plain", "html"] = "plain"


class EmailMessage(BaseModel):
    """
    One email waiting on the email queue.

    Fields mirror EmailService.send_email, so the consumer can hand a message
    straight to it: `email_service.send_email(**message.model_dump())`.
    Parts are rendered before queuing, so the consumer needs no templates.
    """

    recipient: str
    subject: str
    message_parts: list[EmailPart]
    sender_email: str | None = None
