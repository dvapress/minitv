from __future__ import annotations

import logging

from fastapi import FastAPI, Request

from app.api import mount_ui, router
from app.config import Settings, load_settings
from app.db import ensure_admin, ensure_secret, init_db

logger = logging.getLogger("leapdrama")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = ensure_secret(settings or load_settings())
    init_db(settings)
    ensure_admin(settings)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    app = FastAPI(title="LeapDrama", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.state.settings = settings

    @app.middleware("http")
    async def demo_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api") or request.url.path == "/health":
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-LeapDrama-Demo"] = "simulated-payments"
        return response

    app.include_router(router)
    mount_ui(app, settings)
    logger.info("LeapDrama ready on %s:%s", settings.bind, settings.port)
    return app
