from functools import wraps

from src.config.logger import Logger
from src.models.new_db_models import database


def connect_db(func):
    logger = Logger()

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Establish the database connection
            database.connect()
            logger.info("Database connected.")

            # Call the wrapped function
            result = func(*args, **kwargs)

            return result
        finally:
            # Close the database connection
            database.close()
            logger.info("Database connection closed.")

    return wrapper
