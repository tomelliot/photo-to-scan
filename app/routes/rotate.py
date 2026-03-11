from fastapi import APIRouter, Cookie, Response
from fastapi.responses import HTMLResponse
from PIL import Image

from app.rendering import render_thumbnail
from app.sessions import get_session

router = APIRouter()


@router.post("/pages/{page_id}/rotate", response_class=HTMLResponse)
async def rotate_page(
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

    # Rotate image files 90 degrees clockwise on disk
    for path in [page.original, page.processed]:
        if path and path.exists():
            with Image.open(path) as img:
                rotated = img.rotate(-90, expand=True)
                rotated.save(path)

    page.rotation = (page.rotation + 90) % 360

    return render_thumbnail(page)
