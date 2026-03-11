import httpx
from fastapi import APIRouter, Cookie, Response

from app.config import get_settings
from app.routes.assemble import build_pdf
from app.sessions import get_session, delete_session, SESSION_COOKIE

router = APIRouter()


@router.post("/submit")
async def submit(
    response: Response,
    docprep_session: str | None = Cookie(None),
):
    settings = get_settings()
    if not settings.paperless_url or not settings.paperless_token:
        response.status_code = 503
        return {"error": "Paperless-ngx not configured"}

    session = get_session(docprep_session) if docprep_session else None
    if not session or not session.pages:
        response.status_code = 422
        return {"error": "No pages to submit"}

    pdf_bytes = build_pdf(session.pages)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.paperless_url}/api/documents/post_document/",
                headers={"Authorization": f"Token {settings.paperless_token}"},
                files={"document": ("document.pdf", pdf_bytes, "application/pdf")},
                timeout=30,
            )
            resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError):
        response.status_code = 502
        return {"error": "Paperless upload failed"}

    delete_session(session.id)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}
