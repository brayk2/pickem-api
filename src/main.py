import logging

from fastapi import FastAPI
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

app.include_router(api)

handler = Mangum(app)
