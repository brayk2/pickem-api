from typing import Optional

import httpx
from pydantic import BaseModel

from src.config.base_service import BaseService
from src.util.injection import dependency, inject
from queue import Queue


class Request(BaseModel):
    method: str
    url: str
    params: Optional[dict] = None
    data: Optional[dict] = None
    headers: Optional[dict] = None


@dependency
class BufferedClient(BaseService):
    @inject
    def __init__(self, base_url: str):
        self.request_queue = Queue()
        self.base_url = base_url

    @property
    def _client(self):
        return httpx.Client(base_url=self.base_url)

    def _request(self, request: Request):
        self.request_queue.put(request)

    def get(self, *args, **kwargs):
        return self._request()

    def post(self):
        return self._request()

    def put(self):
        return self._request()

    def delete(self):
        return self._request()
