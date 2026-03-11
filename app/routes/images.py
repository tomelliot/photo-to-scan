from fastapi import APIRouter, Cookie, Query, Response
from fastapi.responses import FileResponse

from app.sessions import get_session

router = APIRouter()


@router.get("/pages/{page_id}/image")
async def get_page_image(
    page_id: str,
    response: Response,
    type: str = Query("original"),
    docprep_session: str | None = Cookie(None),
):
    session = get_session(docprep_session) if docprep_session else None
    if not session:
        response.status_code = 404
        return {"error": "Session not found"}

    page = next((p for p in session.pages if p.id == page_id), None)
    if not page:
        response.status_code = 404
        return {"error": "Page not found"}

    if type == "processed" and page.processed and page.processed.exists():
        path = page.processed
    else:
        path = page.original

    return FileResponse(path, media_type="image/jpeg")
