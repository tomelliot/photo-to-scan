import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.cleanup import cleanup_loop
from app.config import get_settings
from app.errors import AppError
from app.sessions import purge_expired_archives
from app.templating import templates
from app.routes.pages import router as pages_router
from app.routes.upload import router as upload_router
from app.routes.process import router as process_router
from app.routes.images import router as images_router
from app.routes.pages_mgmt import router as pages_mgmt_router
from app.routes.rotate import router as rotate_router
from app.routes.assemble import router as assemble_router
from app.routes.submit import router as submit_router
from app.routes.tags import router as tags_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    purge_expired_archives(settings.retention_days)
    task = asyncio.create_task(cleanup_loop(retention_days=settings.retention_days))
    yield
    task.cancel()


async def _render_app_error(request: Request, exc: AppError) -> HTMLResponse:
    # HTMX only processes hx-swap-oob on 2xx responses, so we keep the
    # status at 200 — the modal *is* the intended UI for this error.
    html = templates.get_template("error_modal.html").render(
        title=exc.title, detail=exc.detail
    )
    return HTMLResponse(content=html, status_code=200)


def create_app() -> FastAPI:
    app = FastAPI(title="Paperless Feeder", lifespan=lifespan)
    app.add_exception_handler(AppError, _render_app_error)
    app.get("/health")(health)
    app.include_router(pages_router)
    app.include_router(upload_router)
    app.include_router(process_router)
    app.include_router(images_router)
    app.include_router(pages_mgmt_router)
    app.include_router(rotate_router)
    app.include_router(assemble_router)
    app.include_router(submit_router)
    app.include_router(tags_router)
    return app


async def health():
    return {"status": "ok"}


app = create_app()
