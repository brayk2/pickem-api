from peewee import PostgresqlDatabase
from playhouse.pool import PooledPostgresqlDatabase
from src.config.logger import Logger
from src.config.settings import Settings
from src.services.secret_service import SecretService

logger = Logger()


def get_database() -> PostgresqlDatabase:
    settings = Settings()
    secret_service = SecretService()

    logger.info(f"db name = {settings.db_name}")
    secret = secret_service.get_secret("dev/db")

    return PooledPostgresqlDatabase(
        settings.db_name,
        thread_safe=True,
        host=settings.db_host,
        user=settings.db_user,
        password=secret.get("password"),
        max_connections=20,
        stale_timeout=900,
        sslmode="require",
    )
