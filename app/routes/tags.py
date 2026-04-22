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

    return [{"id": t.id, "name": t.name} for t in tags]
