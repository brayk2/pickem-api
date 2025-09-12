import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os

from src.config.logger import Logger
from src.services.secret_service import SecretService
from src.util.injection import dependency, inject


@dependency
class EmailService:
    @inject
    def __init__(
        self,
        logger: Logger,
        secret_service: SecretService,
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        use_tls=True,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.secret_service = secret_service

        creds = self.secret_service.get_secret(secret_path="email/credentials")
        self.login = creds.get("address")
        self.password = creds.get("password")

        self.use_tls = use_tls
        self.logger = logger

    def send_email(self, recipient, subject, message_parts, sender_email=None):
        """
        Sends an email with the specified message parts.

        Parameters:
        - recipient (str): The recipient's email address.
        - subject (str): The email subject.
        - message_parts (list of dict): A list of message parts in the order they should appear.
            Each part is a dict with 'content' and 'subtype' keys.
            'subtype' can be 'plain', 'html', etc.
        - sender_email (str, optional): The sender's email address. Defaults to the login email.
        """
        sender_email = sender_email or self.login

        # Create a MIMEMultipart message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient
        message["Subject"] = subject

        # Attach each message part in order
        for part in message_parts:
            content = part.get("content")
            subtype = part.get("subtype", "plain")
            mime_part = MIMEText(content, subtype)
            message.attach(mime_part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.login, self.password)
                server.sendmail(sender_email, recipient, message.as_string())
            self.logger.info(f"Email sent successfully to {recipient}")
        except Exception as e:
            self.logger.error(f"Failed to send email to {recipient}: {e}")
            raise
