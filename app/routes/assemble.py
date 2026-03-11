import io

from fastapi import APIRouter, Cookie, Response
from fastapi.responses import StreamingResponse
from PIL import Image

from app.sessions import get_session

router = APIRouter()


def build_pdf(pages) -> bytes:
    """Build a PDF from a list of PageEntry objects. Returns PDF bytes."""
    images = []
    for page in pages:
        path = page.processed if page.processed and page.processed.exists() else page.original
        images.append(Image.open(path).convert("RGB"))

    buf = io.BytesIO()
    first, *rest = images
    first.save(buf, format="PDF", save_all=True, append_images=rest)
    return buf.getvalue()


@router.post("/assemble")
async def assemble(
    response: Response,
    docprep_session: str | None = Cookie(None),
):
    session = get_session(docprep_session) if docprep_session else None
    if not session or not session.pages:
        response.status_code = 422
        return {"error": "No pages to assemble"}

    pdf_bytes = build_pdf(session.pages)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=document.pdf"},
    )
