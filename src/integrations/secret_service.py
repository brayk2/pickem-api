import json
import time
from functools import cached_property

import boto3

from src.config.base_service import BaseService
from src.util.injection import dependency, inject

# Long enough that a warm container stops calling Secrets Manager on every
# request, short enough that a rotated value is picked up without a redeploy.
DEFAULT_MAX_AGE_S = 300

_cache: dict[str, tuple[float, object]] = {}


@dependency
class SecretService(BaseService):
    @inject
    def __init__(self):
        pass

    @cached_property
    def client(self):
        # Building a boto3 client costs tens of milliseconds of CPU; build one.
        return boto3.client(service_name="secretsmanager")

    def get_secret(self, secret_path, max_age_s: float = DEFAULT_MAX_AGE_S):
        """
        :param max_age_s: how stale a cached value may be; 0 always fetches.
        """
        cached = _cache.get(secret_path)
        if cached and time.monotonic() - cached[0] < max_age_s:
            return cached[1]

        secret_string = self.client.get_secret_value(SecretId=secret_path).get(
            "SecretString"
        )
        try:
            value = json.loads(secret_string)
        except json.JSONDecodeError:
            value = secret_string

        _cache[secret_path] = (time.monotonic(), value)
        return value
