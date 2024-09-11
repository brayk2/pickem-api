import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.util.injection import dependency

env = os.getenv("ENVIRONMENT", "dev")


def get_resources_path() -> str:
    parent = Path(__file__).parents[1]
    return str(parent / "resources")


def get_properties_file_path(config_type: str) -> tuple[str, str]:
    return (
        get_resources_path() + f"/{config_type}.properties",
        get_resources_path() + f"/{config_type}.{env}.properties",
    )


@dependency
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=get_properties_file_path(config_type="app")
    )

    secret_path: str
    db_host: str
    db_name: str
    # db_user: str = os.getenv("user", "_")
    # db_pass: str = os.getenv("password", "_")
    # odds_api_key: str = os.getenv("odds_api_key", "_")
