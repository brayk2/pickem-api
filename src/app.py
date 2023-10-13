import functools
import logging

import starlette.requests
from fastapi import FastAPI, APIRouter
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware

from src.api.routes import api

# sql_logger = logging.getLogger("peewee")
# sql_logger.addHandler(logging.StreamHandler())
# sql_logger.setLevel(logging.DEBUG)

app = FastAPI(title="Test Api", version="0.0.1", root_path="/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ping_router = APIRouter(prefix="", tags=["Ping"])


@ping_router.get("/")
def ping():
    return {"hello": "world"}


app.include_router(api)
app.include_router(ping_router)


def dec(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        print(f"args: {args}")
        print(f"kwargs: {kwargs}")
        return f(*args, **kwargs)

    return wrapper


handler = dec(Mangum(app))
