from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Form, Response
from fastapi.responses import HTMLResponse

from app.config import Settings, get_settings
from app.errors import (
    AlreadySubmittedError,
    AlreadySubmittingError,
    NoPagesError,
    PaperlessNotConfiguredError,
    PaperlessRejectedError,
    PaperlessUnreachableError,
)
from app.paperless import PaperlessNotConfigured, paperless_client
from app.routes.assemble import build_pdf
from app.sessions import (
    SESSION_COOKIE,
    Session,
    SessionStatus,
    archive_session,
    optional_session,
    set_session_status,
)

router = APIRouter()


@router.post("/submit", response_class=HTMLResponse)
async def submit(
    response: Response,
    session: Session | None = Depends(optional_session),
    settings: Settings = Depends(get_settings),
    tags: list[int] = Form(default_factory=list),
):
    if not session or not session.pages:
        raise NoPagesError

    if session.status == SessionStatus.SUBMITTING:
        raise AlreadySubmittingError
    if session.status == SessionStatus.SUBMITTED:
        raise AlreadySubmittedError

    pdf_bytes = build_pdf(session.pages)
    filename = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".pdf"

    set_session_status(session.id, SessionStatus.SUBMITTING)
    try:
        async with paperless_client(settings) as pp:
            await pp.post_document(pdf_bytes, tags, filename)
    except PaperlessNotConfigured:
        set_session_status(session.id, SessionStatus.DRAFT)
        raise PaperlessNotConfiguredError
    except httpx.HTTPStatusError as exc:
        set_session_status(session.id, SessionStatus.DRAFT)
        raise PaperlessRejectedError(exc.response.status_code)
    except httpx.RequestError as exc:
        set_session_status(session.id, SessionStatus.DRAFT)
        raise PaperlessUnreachableError(settings.paperless_url, type(exc).__name__)

    set_session_status(session.id, SessionStatus.SUBMITTED)
    archive_session(session.id, reason="submitted")
    response.delete_cookie(SESSION_COOKIE)

    # OOB swap to clear the page list back to starting state
    return (
        '<div id="page-list" hx-swap-oob="innerHTML">'
        '<label class="add-btn flex-shrink-0 w-24 h-24 flex items-center justify-center '
        'bg-white border-2 border-dashed border-gray-300 rounded-lg cursor-pointer '
        'hover:border-blue-400 hover:bg-blue-50 transition-colors">'
        '<svg class="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>'
        '</svg>'
        '<input type="file" accept="image/*" capture="environment" class="hidden" '
        'hx-post="/upload" hx-target="#page-list .add-btn" hx-swap="beforebegin" '
        'hx-encoding="multipart/form-data" name="file">'
        '</label></div>'
    )
