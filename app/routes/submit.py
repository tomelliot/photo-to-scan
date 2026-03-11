from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Cookie, Response
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.routes.assemble import build_pdf
from app.sessions import get_session, delete_session, SESSION_COOKIE

router = APIRouter()


def _error_html(title: str, detail: str) -> str:
    return (
        '<div id="error-modal" hx-swap-oob="innerHTML">'
        '<div class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"'
        ' onclick="if(event.target===this){document.getElementById(\'error-modal\').innerHTML=\'\'}">'
        '<div class="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">'
        f'<h2 class="text-lg font-semibold text-red-600 mb-2">{title}</h2>'
        f'<p class="text-gray-600 text-sm mb-4">{detail}</p>'
        '<button onclick="document.getElementById(\'error-modal\').innerHTML=\'\'"'
        ' class="w-full bg-gray-800 text-white py-2 rounded-lg font-medium">Dismiss</button>'
        '</div></div></div>'
    )


@router.post("/submit", response_class=HTMLResponse)
async def submit(
    response: Response,
    docprep_session: str | None = Cookie(None),
):
    settings = get_settings()
    if not settings.paperless_url or not settings.paperless_token:
        return _error_html(
            "Not configured",
            "Paperless-ngx URL and API token are not set. "
            "Configure PAPERLESS_URL and PAPERLESS_TOKEN environment variables.",
        )

    session = get_session(docprep_session) if docprep_session else None
    if not session or not session.pages:
        return _error_html("No pages", "Add at least one page before submitting.")

    pdf_bytes = build_pdf(session.pages)

    try:
        async with httpx.AsyncClient(
            base_url=settings.paperless_url,
            headers={"Authorization": f"Token {settings.paperless_token}"},
            follow_redirects=True,
            timeout=30,
        ) as client:
            filename = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".pdf"
            resp = await client.post(
                "/api/documents/post_document/",
                files={"document": (filename, pdf_bytes, "application/pdf")},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return _error_html(
            "Upload failed",
            f"Paperless-ngx returned status {exc.response.status_code}. "
            "Check that the URL and token are correct.",
        )
    except httpx.RequestError as exc:
        return _error_html(
            "Connection error",
            f"Could not reach Paperless-ngx at {settings.paperless_url}. "
            f"Details: {type(exc).__name__}",
        )

    delete_session(session.id)
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
