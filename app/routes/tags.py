"""Proxy endpoint exposing Paperless-ngx tags to the frontend."""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.paperless import PaperlessNotConfigured, paperless_client

router = APIRouter()


@router.get("/tags")
async def list_tags(settings: Settings = Depends(get_settings)):
    try:
        async with paperless_client(settings) as pp:
            tags = await pp.list_tags()
    except PaperlessNotConfigured:
        raise HTTPException(status_code=503, detail="Paperless-ngx not configured")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Paperless-ngx returned {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Paperless-ngx: {type(exc).__name__}",
        )

    # Most-used tags first so the labels the user reaches for sit at the top of
    # the picker; name breaks ties so the order is stable between requests.
    # Sorted here rather than via a Paperless `ordering=` param so the result
    # doesn't depend on the remote's sort support, and applies across all pages.
    tags = sorted(tags, key=lambda t: (-t.document_count, t.name.lower()))

    return [{"id": t.id, "name": t.name} for t in tags]
