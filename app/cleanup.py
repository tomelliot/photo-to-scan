"""Background task to clean up expired sessions."""

import asyncio
import logging
from time import time

from app.sessions import get_all_sessions, archive_session, purge_expired_archives

logger = logging.getLogger(__name__)

DEFAULT_TTL = 3600  # 1 hour
DEFAULT_INTERVAL = 300  # 5 minutes


def cleanup_expired_sessions(ttl: float = DEFAULT_TTL) -> list[str]:
    """Archive in-memory sessions inactive longer than ttl seconds. Returns list of archived session IDs."""
    now = time()
    removed = []
    for sid, session in list(get_all_sessions().items()):
        if now - session.last_active > ttl:
            archive_session(sid, reason="expired")
            removed.append(sid)
    return removed


async def cleanup_loop(
    ttl: float = DEFAULT_TTL,
    interval: float = DEFAULT_INTERVAL,
    retention_days: int | None = None,
):
    """Periodically archive expired sessions and purge old archives."""
    while True:
        await asyncio.sleep(interval)
        # Pass 1: archive in-memory sessions that exceeded TTL
        cleanup_expired_sessions(ttl)
        # Pass 2: purge archived session dirs past retention
        purge_expired_archives(retention_days)
