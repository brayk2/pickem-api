from peewee import PostgresqlDatabase
from playhouse.pool import PooledPostgresqlDatabase

from src.config.logger import Logger
from src.config.settings import Settings


logger = Logger()


def get_database() -> PostgresqlDatabase:
    settings = Settings()
    logger.info(f"db name = {settings.db_name}")

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
    logger.info(f"db name = {settings.db_name}")

    return PooledPostgresqlDatabase(
        settings.db_name,
        thread_safe=True,
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        max_connections=20,
        stale_timeout=900,
        sslmode="require",
    )
