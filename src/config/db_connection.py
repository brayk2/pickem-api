from peewee import PostgresqlDatabase
from playhouse.pool import PooledPostgresqlDatabase

from src.config.logger import Logger
from src.config.settings import Settings


def get_database() -> PostgresqlDatabase:
    settings = Settings()
    return PooledPostgresqlDatabase(
        settings.db_name,
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        max_connections=20,  # Maximum number of connections in the pool
        stale_timeout=300,
        sslmode="require",
    )


logger = Logger()


def get_new_database() -> PostgresqlDatabase:
    settings = Settings()
    return PooledPostgresqlDatabase(
        settings.db_name,
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        max_connections=20,
        stale_timeout=None,
        connection_timeout=None,
        sslmode="require",
    )
