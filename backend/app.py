from fastapi import FastAPI
from backend.core.config import settings
from backend.api.routes.prospects import router as prospects_router
from backend.api.routes.calls import router as calls_router


def create_app() -> FastAPI:
    app = FastAPI(title="Insurance Outreach API", version="0.1.0")
    app.include_router(prospects_router, prefix="/prospects", tags=["prospects"])
    app.include_router(calls_router, tags=["calls"])  # /schedule_call

    @app.get("/healthz")
    async def health() -> dict:
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.VERSION}

    return app


# Expose a module-level app instance for uvicorn and tests
app = create_app()
