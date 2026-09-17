import json

import boto3

from src.config.base_service import BaseService
from src.util.injection import dependency, inject


@dependency
class SecretService(BaseService):
    @inject
    def __init__(self):
        pass

    @property
    def client(self):
        return boto3.client(service_name="secretsmanager")

    def get_secret(self, secret_path):
        secret_string = self.client.get_secret_value(SecretId=secret_path).get(
            "SecretString"
        )
        try:
            return json.loads(secret_string)
        except json.JSONDecodeError:
            return secret_string
