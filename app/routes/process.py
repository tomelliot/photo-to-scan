import logging

import cv2
from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse

from app.processing import run_scan
from app.rendering import render_thumbnail
from app.sessions import Session, require_session

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/process/{page_id}", response_class=HTMLResponse)
async def process_page(
    page_id: str,
    response: Response,
    session: Session = Depends(require_session),
):
    page = next((p for p in session.pages if p.id == page_id), None)
    if not page:
        response.status_code = 404
        return "<p>Page not found.</p>"

    image = cv2.imread(str(page.original))

    try:
        result = run_scan(image)
    except Exception:
        log.exception("Scan failed for page %s", page_id)
        page.status = "done"
        return render_thumbnail(page)

    processed_path = page.original.with_name(f"{page.id}_processed.jpg")
    cv2.imwrite(str(processed_path), result)

    page.processed = processed_path
    page.status = "done"

    return render_thumbnail(page)
