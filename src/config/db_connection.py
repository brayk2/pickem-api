from peewee import PostgresqlDatabase

from src.config.logger import Logger
from src.config.settings import Settings


def get_database() -> PostgresqlDatabase:
    settings = Settings()
    return PostgresqlDatabase(
        settings.db_name,
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        sslmode="require",
    )


logger = Logger()


def get_new_database() -> PostgresqlDatabase:
    logger.info("getting database connection")
    settings = Settings()
    return PostgresqlDatabase(
        settings.db_name,
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        sslmode="require",
    )
