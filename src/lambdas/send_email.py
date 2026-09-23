"""
Consumer for the email queue: sends each queued EmailMessage over SMTP.

Triggered by an SQS event source mapping with ReportBatchItemFailures on, so a
failed email is retried on its own rather than resending the whole batch.
Messages that keep failing land in the queue's dead-letter queue.

No database connection: messages arrive fully rendered.
"""

from pydantic import ValidationError

from src.components.email.email_models import EmailMessage
from src.components.email.email_service import EmailService
from src.config.logger import Logger

logger = Logger()

# Built on first use and kept for the life of the container, so the SMTP
# credentials are fetched once per cold start rather than once per message.
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


def send(record: dict) -> None:
    message = EmailMessage.model_validate_json(record["body"])
    get_email_service().send_email(**message.model_dump())
    logger.info(f"Sent message {record['messageId']} to {message.recipient}")


def handle_event(event, context):
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            send(record)
        except ValidationError as e:
            # Retrying won't fix a malformed message, but reporting it still
            # routes it to the dead-letter queue where it can be inspected,
            # rather than silently dropping it.
            logger.error(f"Message {message_id} is not a valid EmailMessage: {e}")
            failures.append({"itemIdentifier": message_id})
        except Exception as e:
            logger.error(f"Failed to send message {message_id}: {e}")
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
