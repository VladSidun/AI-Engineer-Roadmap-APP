from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.api.boundary import Boundary, error
from app.api.routes import api
from app.config import Config
from app.db.session import connect, ensure_learner
from app.domain.content import Content
from app.domain.engine import Problem


def create_app(config: Config | None = None, engine: Engine | None = None) -> FastAPI:
    cfg = config or Config.from_env()

    @asynccontextmanager
    async def open_app(app: FastAPI) -> AsyncIterator[None]:
        app.state.content = Content()
        db_engine = engine or connect()
        app.state.engine = db_engine
        try:
            with Session(db_engine) as db, db.begin():
                ensure_learner(db)
            yield
        finally:
            if engine is None:
                db_engine.dispose()

    application = FastAPI(lifespan=open_app, docs_url=None, redoc_url=None, openapi_url=None,
                          redirect_slashes=False)
    application.state.config = cfg
    application.add_middleware(Boundary, config=cfg)
    application.include_router(api)

    @application.exception_handler(Problem)
    async def rejected(_: Request, exc: Problem) -> JSONResponse:
        return error(exc.status, exc.code)

    @application.exception_handler(RequestValidationError)
    async def invalid(_: Request, __: RequestValidationError) -> JSONResponse:
        return error(422, "invalid_input")

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return error(exc.status_code, "not_found" if exc.status_code == 404 else "request_rejected")

    @application.exception_handler(SQLAlchemyError)
    async def db_error(_: Request, __: SQLAlchemyError) -> JSONResponse:
        return error(503, "database_unavailable")

    @application.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health")
    def health(request: Request) -> dict[str, str]:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM learner LIMIT 1"))
        return {"status": "ready", "contentVersion": request.app.state.content.manifest.curriculumVersion}

    if cfg.static:
        application.mount("/assets", StaticFiles(directory=cfg.static / "assets"), name="assets")

        @application.get("/{path:path}", response_model=None)
        def web(path: str) -> FileResponse | JSONResponse:
            if path and path.split("/")[0] not in {
                "campaign", "regions", "stages", "lessons", "gates", "reviews", "settings",
            }:
                return error(404, "not_found")
            assert cfg.static
            return FileResponse(cfg.static / "index.html", headers={"Cache-Control": "no-cache"})

    return application


app = create_app()
