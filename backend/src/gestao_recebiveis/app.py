import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.middleware.base import RequestResponseEndpoint
from swagger_ui_bundle import swagger_ui_path

from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import SessionLocal, engine
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.request_limits import RequestBodyLimitMiddleware
from gestao_recebiveis.routes import router

logger = logging.getLogger("gestao_recebiveis.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    get_settings().validate_runtime()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Gestão de recebíveis",
    version="1.0.0",
    description="Contas a receber e lembretes simulados.",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.include_router(router)
app.add_middleware(RequestBodyLimitMiddleware)
app.mount("/assets/swagger", StaticFiles(directory=swagger_ui_path), name="swagger")


@app.get("/docs", include_in_schema=False)
def docs() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Gestão de recebíveis · API",
        swagger_js_url="/assets/swagger/swagger-ui-bundle.js",
        swagger_css_url="/assets/swagger/swagger-ui.css",
        swagger_favicon_url="/assets/swagger/favicon-32x32.png",
    )


@app.middleware("http")
async def response_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation",
            "message": "Confira os campos informados.",
            "details": details,
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("database_conflict path=%s", request.url.path)
    return JSONResponse(
        status_code=409,
        content={
            "code": "database_conflict",
            "message": "Conflito com dados existentes. Recarregue e tente novamente.",
        },
    )


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def database_error(request: Request, exc: OperationalError | PoolTimeout) -> JSONResponse:
    logger.error("database_unavailable path=%s", request.url.path)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "2"},
        content={
            "code": "database_unavailable",
            "message": "Banco indisponível. Tente novamente.",
        },
    )


@app.get("/health", tags=["Operação"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["Operação"])
def ready() -> dict[str, str]:
    with SessionLocal() as session:
        session.execute(text("SELECT 1 FROM alembic_version"))
    return {"status": "ready"}
