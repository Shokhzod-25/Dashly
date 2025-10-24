from fastapi import FastAPI
from src.api import router


def create_app() -> FastAPI:
    app = FastAPI(title="Dashly API", docs_url="/")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    return app
