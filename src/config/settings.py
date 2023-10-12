import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # TODO: hardcoded for now, should use config files
    db_host: str = "ep-wild-wildflower-09765888.us-east-2.aws.neon.tech"
    db_name: str = "pickem"
    db_user: str = os.getenv("user")
    db_pass: str = os.getenv("password")
    odds_api_key: str = os.getenv("odds_api_key")
