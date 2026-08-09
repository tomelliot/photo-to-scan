"""Client for the Paperless-ngx external API.

Owns the `httpx.AsyncClient` configuration for every outbound Paperless call.
Callers open `async with paperless_client(settings) as pp` and invoke typed
methods; they do not touch `httpx` directly.

This exists so the set of invariants we care about for Paperless calls —
`base_url`, `follow_redirects=True`, auth header, request timeout — lives in
exactly one place. See STANDARDS.md rule 1.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from app.config import Settings


_DEFAULT_TIMEOUT_SECONDS = 30


class PaperlessNotConfigured(Exception):
    """Raised when Paperless URL / token are missing from settings."""


@dataclass(frozen=True)
class Tag:
    id: int
    name: str
    document_count: int = 0


class PaperlessClient:
    """Typed wrapper over an `httpx.AsyncClient` pointed at Paperless-ngx.

    Do not construct directly; use `paperless_client(settings)`.
    """

    def __init__(self, transport: httpx.AsyncClient):
        self._transport = transport

    async def list_tags(self) -> list[Tag]:
        tags: list[Tag] = []
        url: str | None = "/api/tags/?page_size=200"
        while url:
            resp = await self._transport.get(url)
            resp.raise_for_status()
            payload = resp.json()
            tags.extend(
                # `document_count` is only present when Paperless is asked for
                # it (and is absent on older versions), so default to 0 rather
                # than KeyError on a tag list we can otherwise use.
                Tag(
                    id=t["id"],
                    name=t["name"],
                    document_count=t.get("document_count", 0),
                )
                for t in payload.get("results", [])
            )
            url = payload.get("next")
        return tags

    async def post_document(
        self,
        pdf_bytes: bytes,
        tag_ids: list[int],
        filename: str,
    ) -> None:
        post_kwargs: dict = {
            "files": {"document": (filename, pdf_bytes, "application/pdf")},
        }
        if tag_ids:
            # NOTE: the shape `{"tags": [...]}` (dict-with-list) is load-bearing
            # for httpx 0.28. Passing `[("tags", v), ("tags", v)]` (list of
            # tuples) — the equivalent shape for repeated form fields — raises
            # `RuntimeError: Attempted to send an sync request with an
            # AsyncClient instance.` Both shapes serialise identically on the
            # wire (tags=1&tags=2), but only the dict form produces an
            # AsyncByteStream inside AsyncClient's multipart encoder.
            post_kwargs["data"] = {"tags": [str(tid) for tid in tag_ids]}
        resp = await self._transport.post(
            "/api/documents/post_document/", **post_kwargs
        )
        resp.raise_for_status()


@asynccontextmanager
async def paperless_client(settings: Settings) -> AsyncIterator[PaperlessClient]:
    """Open a configured `PaperlessClient`.

    Raises `PaperlessNotConfigured` if URL or token are missing. Callers that
    surface a user-facing error decide the error shape themselves (HTML modal,
    HTTP status, etc.).
    """
    if not settings.paperless_url or not settings.paperless_token:
        raise PaperlessNotConfigured()

    async with httpx.AsyncClient(
        base_url=settings.paperless_url,
        headers={"Authorization": f"Token {settings.paperless_token}"},
        follow_redirects=True,
        timeout=_DEFAULT_TIMEOUT_SECONDS,
    ) as transport:
        yield PaperlessClient(transport)
