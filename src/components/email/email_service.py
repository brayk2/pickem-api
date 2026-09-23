import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from src.config.base_service import BaseService
from src.config.logger import Logger
from src.integrations.secret_service import SecretService
from src.util.injection import dependency, inject

# Templates live in ./templates as <name>.html + <name>.txt pairs, and inherit
# from base.html. Loaded through the package rather than a filesystem path so
# they resolve the same locally, in the Docker image and in the Lambda zip.
_templates = Environment(
    loader=PackageLoader("src.components.email", "templates"),
    # User-supplied values (names, emails) are escaped in HTML, never in text.
    autoescape=select_autoescape(["html"]),
    # A misspelled variable fails the render instead of sending a blank.
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dependency
class EmailService(BaseService):
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

    @staticmethod
    def render_template(template: str, **context) -> list[dict]:
        """
        Renders a template pair into message parts for send_email.

        Render once and reuse the parts when the same email goes to many people.

        :param template: The template name, without extension -- e.g.
            "password_reset" renders password_reset.txt and password_reset.html.
        :param context: The variables the template expects.
        """
        return [
            {
                "content": _templates.get_template(f"{template}.txt").render(**context),
                "subtype": "plain",
            },
            {
                "content": _templates.get_template(f"{template}.html").render(
                    **context
                ),
                "subtype": "html",
            },
        ]

    def send_email(self, recipient, subject, message_parts, sender_email=None):
        """
        Sends an email with the specified message parts.

        Parameters:
        - recipient (str): The recipient's email address.
        - subject (str): The email subject.
        - message_parts (list of dict): Alternative versions of the same message,
            least preferred first -- plain text, then HTML. The client shows the
            last one it can render, not all of them.
            Each part is a dict with 'content' and 'subtype' keys.
        - sender_email (str, optional): The sender's email address. Defaults to the login email.
        """
        sender_email = sender_email or self.login

        # "alternative" so a client shows the HTML or the text, not both stacked
        message = MIMEMultipart("alternative")
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
