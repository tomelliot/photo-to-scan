import uuid

from fastapi import APIRouter, Cookie, UploadFile, File, Response
from fastapi.responses import HTMLResponse

from app.rendering import render_thumbnail_processing
from app.sessions import (
    SESSION_COOKIE,
    PageEntry,
    get_or_create_session,
)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post("/upload", response_class=HTMLResponse)
async def upload(
    response: Response,
    file: UploadFile = File(...),
    docprep_session: str | None = Cookie(None),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        response.status_code = 422
        return "<p>Only image files are accepted.</p>"

    session = get_or_create_session(docprep_session)
    response.set_cookie(SESSION_COOKIE, session.id)

    page_id = uuid.uuid4().hex[:12]
    ext = _ext_from_content_type(file.content_type)
    original_path = session.work_dir / f"{page_id}_original{ext}"

    content = await file.read()
    original_path.write_bytes(content)

    page = PageEntry(id=page_id, original=original_path)
    session.pages.append(page)

    return render_thumbnail_processing(page)


def _ext_from_content_type(ct: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    return mapping.get(ct, ".jpg")
