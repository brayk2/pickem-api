import json
from functools import cached_property

import boto3
from pydantic import BaseModel

from src.components.email.email_models import EmailMessage
from src.config.base_service import BaseService
from src.util.injection import dependency, inject


@dependency
class QueueService(BaseService):
    @inject
    def __init__(self):
        # Queue URLs never change for a given name, so look each one up once
        # per container rather than on every send.
        self._queue_urls: dict[str, str] = {}

    @cached_property
    def client(self):
        return boto3.client(service_name="sqs")

    def get_queue_url(self, queue_name: str) -> str:
        if queue_name not in self._queue_urls:
            self._queue_urls[queue_name] = self.client.get_queue_url(
                QueueName=queue_name
            )["QueueUrl"]
        return self._queue_urls[queue_name]

    def send_message(
        self, queue_name: str, message: BaseModel | dict, delay_seconds: int = 0
    ) -> str:
        """
        Puts one JSON message on a queue.

        :param queue_name: The queue's name, not its URL.
        :param message: A pydantic model or a JSON-serializable dict.
        :param delay_seconds: How long SQS hides the message before it can be
            received, 0-900.
        :return: The SQS message id.
        """
        body = (
            message.model_dump_json()
            if isinstance(message, BaseModel)
            else json.dumps(message)
        )

        response = self.client.send_message(
            QueueUrl=self.get_queue_url(queue_name),
            MessageBody=body,
            DelaySeconds=delay_seconds,
        )

        # The body is deliberately not logged: emails carry things like
        # password reset links.
        message_id = response["MessageId"]
        self.logger.info(f"Queued message {message_id} on {queue_name}")
        return message_id

    def send_email(self, email: EmailMessage) -> str:
        """Queues an email for the email lambda to send."""
        self.logger.info(f"Queueing email '{email.subject}' to {email.recipient}")
        return self.send_message(queue_name=self.settings.email_queue, message=email)
