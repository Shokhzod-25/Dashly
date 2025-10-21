from fastapi import FastAPI
from src.api import router


def create_app() -> FastAPI:
    app = FastAPI(title="Dashly API", docs_url="/")
    app.include_router(router)

    return app
