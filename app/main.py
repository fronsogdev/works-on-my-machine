"""FastAPI application: routes, lifespan wiring and the static front page."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import redis
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker, get_session
from app.excuses import random_excuse
from app.logging_setup import configure_logging, get_logger
from app.metrics import read_render_durations, render_metrics_text
from app.models import STATUS_DONE, STATUS_FAILED, Certificate
from app.schemas import (
    CertificateCreated,
    CertificateRequest,
    CertificateStatus,
    HallOfShameEntry,
)
from app.task_queue import create_queue, create_redis, enqueue_render, queue_depth

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared resources on startup and release them on shutdown.

    uvicorn translates SIGTERM into lifespan shutdown, so this is where graceful
    shutdown happens: in-flight requests finish, then the engine and Redis
    connection are closed.
    """
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    log = get_logger()
    log.info("startup", queue_name=settings.queue_name)

    if app.state.engine is None:
        app.state.engine = create_engine(settings)
        app.state.owns_engine = True
    app.state.sessionmaker = create_sessionmaker(app.state.engine)

    if app.state.redis is None:
        app.state.redis = create_redis(settings)
        app.state.owns_redis = True
    app.state.queue = create_queue(settings, app.state.redis)

    yield

    log.info("shutdown")
    if app.state.owns_engine:
        await app.state.engine.dispose()
    if app.state.owns_redis:
        app.state.redis.close()


def _status_payload(certificate: Certificate) -> CertificateStatus:
    return CertificateStatus(
        id=certificate.id,
        status=certificate.status,
        name=certificate.name,
        project=certificate.project,
        excuse=certificate.excuse,
        serial_number=certificate.serial_number,
        notary=certificate.notary,
        job_id=certificate.job_id,
        created_at=certificate.created_at,
        issued_at=certificate.issued_at,
        image_url=f"/certificates/{certificate.id}" if certificate.status == STATUS_DONE else None,
    )


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    redis_conn: redis.Redis | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    ``engine`` and ``redis_conn`` let the test suite inject in-memory SQLite and
    fakeredis without touching the network.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="Works On My Machine Certification Authority",
        version="0.1.0",
        summary="Issue official-looking proof that your code works. On a machine.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.redis = redis_conn
    app.state.owns_engine = engine is None
    app.state.owns_redis = redis_conn is None

    @app.post("/certificates", status_code=202, response_model=CertificateCreated)
    async def create_certificate(
        payload: CertificateRequest,
        request: Request,
        session: SessionDep,
    ) -> CertificateCreated:
        certificate = Certificate(
            id=str(uuid.uuid4()),
            name=payload.name,
            project=payload.project,
            excuse=payload.excuse,
        )
        session.add(certificate)
        await session.commit()

        try:
            job = await run_in_threadpool(
                enqueue_render,
                request.app.state.queue,
                certificate.id,
                job_timeout=settings.job_timeout,
            )
        except Exception:
            certificate.status = STATUS_FAILED
            await session.commit()
            get_logger().exception("enqueue_failed", certificate_id=certificate.id)
            raise HTTPException(status_code=503, detail="The queue is on a coffee break.") from None

        certificate.job_id = job.id
        await session.commit()
        return CertificateCreated(
            id=certificate.id, status=certificate.status, job_id=certificate.job_id
        )

    @app.get("/certificates/{certificate_id}")
    async def get_certificate(
        certificate_id: str,
        session: SessionDep,
        output: str = Query(
            default="auto",
            pattern="^(auto|json)$",
            description="'auto' returns the PNG once done, 'json' always returns metadata.",
        ),
    ) -> Response:
        certificate = await session.get(Certificate, certificate_id)
        if certificate is None:
            raise HTTPException(status_code=404, detail="That certificate never happened.")
        if output == "json" or certificate.status != STATUS_DONE or certificate.image_png is None:
            return JSONResponse(content=_status_payload(certificate).model_dump(mode="json"))
        return Response(
            content=certificate.image_png,
            media_type="image/png",
            headers={"X-Certificate-Status": certificate.status},
        )

    @app.get("/hall-of-shame", response_model=list[HallOfShameEntry])
    async def hall_of_shame(session: SessionDep) -> list[HallOfShameEntry]:
        result = await session.scalars(
            select(Certificate)
            .where(Certificate.status == STATUS_DONE)
            .order_by(Certificate.issued_at.desc().nullslast())
            .limit(20)
        )
        return [
            HallOfShameEntry(
                name=certificate.name,
                project=certificate.project,
                excuse=certificate.excuse,
                serial_number=certificate.serial_number,
                issued_at=certificate.issued_at,
            )
            for certificate in result
        ]

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness: the process is up. Never touches dependencies."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request, session: SessionDep) -> Response:
        """Readiness: both Postgres and Redis must answer."""
        problems: list[str] = []
        try:
            await session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            problems.append(f"database: {exc}")
        try:
            await run_in_threadpool(request.app.state.redis.ping)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            problems.append(f"redis: {exc}")
        if problems:
            return JSONResponse(
                status_code=503,
                content={"status": "unready", "problems": problems},
            )
        return JSONResponse(content={"status": "ready"})

    @app.get("/metrics")
    async def metrics(request: Request, session: SessionDep) -> Response:
        """Prometheus text exposition.

        Counts come from the database (single source of truth), queue depth
        from the RQ list, and the render histogram from the bounded Redis list
        written by the worker.
        """
        issued_total = int(
            await session.scalar(
                select(func.count())
                .select_from(Certificate)
                .where(Certificate.status == STATUS_DONE)
            )
            or 0
        )
        depth = await run_in_threadpool(queue_depth, request.app.state.redis, settings.queue_name)
        durations = await run_in_threadpool(read_render_durations, request.app.state.redis)
        content = render_metrics_text(
            issued_total=issued_total,
            queue_depth=depth,
            durations_ms=durations,
        )
        return Response(content=content, media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        get_logger(path=request.url.path, method=request.method).exception("unhandled_error")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "excuse": random_excuse()},
        )

    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="front-page")

    return app


app = create_app()
