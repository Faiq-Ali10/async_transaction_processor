from fastapi import FastAPI

from app.api.routers.jobs import router as jobs_router
from app.core.database import Base, engine
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(jobs_router)

    @app.on_event("startup")
    def startup_event() -> None:
        Base.metadata.create_all(bind=engine)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
