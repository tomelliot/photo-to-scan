"""Proxy endpoint exposing Paperless-ngx tags to the frontend."""

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings

router = APIRouter()


@router.get("/tags")
async def list_tags():
    settings = get_settings()
    if not settings.paperless_url or not settings.paperless_token:
        raise HTTPException(status_code=503, detail="Paperless-ngx not configured")

    tags: list[dict] = []
    try:
        async with httpx.AsyncClient(
            base_url=settings.paperless_url,
            headers={"Authorization": f"Token {settings.paperless_token}"},
            follow_redirects=True,
            timeout=10,
        ) as client:
            url = "/api/tags/?page_size=200"
            while url:
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
                tags.extend(payload.get("results", []))
                url = payload.get("next")
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

    return [{"id": t["id"], "name": t["name"]} for t in tags]
