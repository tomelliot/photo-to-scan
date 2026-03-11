import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.cleanup import cleanup_loop
from app.routes.pages import router as pages_router
from app.routes.upload import router as upload_router
from app.routes.process import router as process_router
from app.routes.images import router as images_router
from app.routes.pages_mgmt import router as pages_mgmt_router
from app.routes.rotate import router as rotate_router
from app.routes.assemble import router as assemble_router
from app.routes.submit import router as submit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="Paperless Feeder", lifespan=lifespan)
    app.get("/health")(health)
    app.include_router(pages_router)
    app.include_router(upload_router)
    app.include_router(process_router)
    app.include_router(images_router)
    app.include_router(pages_mgmt_router)
    app.include_router(rotate_router)
    app.include_router(assemble_router)
    app.include_router(submit_router)
    return app


async def health():
    return {"status": "ok"}


app = create_app()
