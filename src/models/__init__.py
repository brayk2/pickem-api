from src.config.db_connection import get_database


def fetch_models():
    # Imported lazily: src.models.db_models opens a database connection at import
    # time, and this package is also the entry point for db-free modules like
    # src.models.base_models.
    import src.models.db_models as db_models

    return db_models.BaseModel.__subclasses__()


def init_tables():
    with get_database() as db:
        db.create_tables(fetch_models())


if __name__ == "__main__":
    init_tables()
