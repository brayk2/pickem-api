from functools import wraps

from src.models.new_db_models import database


def connect_db(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Establish the database connection
            database.connect()
            print("Database connected.")

            # Call the wrapped function
            result = func(*args, **kwargs)

            return result
        finally:
            # Close the database connection
            database.close()
            print("Database connection closed.")

    return wrapper
