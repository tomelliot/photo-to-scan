import shutil

from fastapi import APIRouter, Cookie, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.rendering import render_thumbnail
from app.sessions import get_session

router = APIRouter()


class ReorderRequest(BaseModel):
    order: list[str]


@router.delete("/pages/{page_id}", response_class=HTMLResponse)
async def delete_page(
    page_id: str,
    response: Response,
    docprep_session: str | None = Cookie(None),
):
    session = get_session(docprep_session) if docprep_session else None
    if not session:
        response.status_code = 404
        return "<p>Session not found.</p>"

    page = next((p for p in session.pages if p.id == page_id), None)
    if not page:
        response.status_code = 404
        return "<p>Page not found.</p>"

    session.pages.remove(page)
    # Clean up files
    for path in [page.original, page.processed]:
        if path and path.exists():
            path.unlink()

    return _render_page_list(session.pages)


@router.put("/pages/reorder", response_class=HTMLResponse)
async def reorder_pages(
    body: ReorderRequest,
    response: Response,
    docprep_session: str | None = Cookie(None),
):
    session = get_session(docprep_session) if docprep_session else None
    if not session:
        response.status_code = 404
        return "<p>Session not found.</p>"

    page_map = {p.id: p for p in session.pages}
    if not all(pid in page_map for pid in body.order):
        response.status_code = 422
        return "<p>Invalid page IDs.</p>"

    session.pages = [page_map[pid] for pid in body.order]
    return _render_page_list(session.pages)


def _render_page_list(pages) -> str:
    if not pages:
        return '<div id="page-list"></div>'
    parts = [render_thumbnail(p) for p in pages]
    return '<div id="page-list">' + "".join(parts) + "</div>"
