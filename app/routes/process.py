import cv2
from fastapi import APIRouter, Cookie, Response
from fastapi.responses import HTMLResponse

from app.processing import run_scan
from app.rendering import render_thumbnail
from app.sessions import get_session

router = APIRouter()


@router.post("/process/{page_id}", response_class=HTMLResponse)
async def process_page(
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

    image = cv2.imread(str(page.original))
    result = run_scan(image)

    processed_path = page.original.with_name(f"{page.id}_processed.jpg")
    cv2.imwrite(str(processed_path), result)

    page.processed = processed_path
    page.status = "done"

    return render_thumbnail(page)
