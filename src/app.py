from fastapi import FastAPI
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware
from src.api.routes import api
from src.api.routes.ping_router import ping_router

app = FastAPI(title="PickEm Api", version="0.0.1", root_path="/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


app.include_router(api)
app.include_router(ping_router)


handler = Mangum(app)
