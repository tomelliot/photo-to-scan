from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse

from app.sessions import Session, require_session

router = APIRouter()


@router.get("/pages/{page_id}/image")
async def get_page_image(
    page_id: str,
    response: Response,
    type: str = Query("original"),
    session: Session = Depends(require_session),
):
    page = next((p for p in session.pages if p.id == page_id), None)
    if not page:
        response.status_code = 404
        return {"error": "Page not found"}

    if type == "processed" and page.processed and page.processed.exists():
        path = page.processed
    else:
        path = page.original

    return FileResponse(path, media_type="image/jpeg")
