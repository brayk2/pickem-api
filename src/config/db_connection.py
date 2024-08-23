from peewee import PostgresqlDatabase
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


def get_new_database() -> PostgresqlDatabase:
    settings = Settings()
    return PostgresqlDatabase(
        settings.db_name,
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        sslmode="require",
    )
