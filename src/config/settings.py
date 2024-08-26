import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # TODO: hardcoded for now, should use config files
    # db_host: str = "ep-wild-wildflower-09765888-pooler.us-east-2.aws.neon.tech"
    db_host: str = "ep-wild-wildflower-09765888.us-east-2.aws.neon.tech"
    db_name: str = "pickem_refactor"
    db_user: str = os.getenv("user", "_")
    db_pass: str = os.getenv("password", "_")
    odds_api_key: str = os.getenv("odds_api_key", "_")
    secret_path: str = "dev/oauth"
