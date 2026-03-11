"""Background task to clean up expired sessions."""

import asyncio
from time import time

from app.sessions import get_all_sessions, delete_session

DEFAULT_TTL = 3600  # 1 hour
DEFAULT_INTERVAL = 300  # 5 minutes


def cleanup_expired_sessions(ttl: float = DEFAULT_TTL) -> list[str]:
    """Remove sessions older than ttl seconds. Returns list of removed session IDs."""
    now = time()
    removed = []
    for sid, session in list(get_all_sessions().items()):
        if now - session.last_active > ttl:
            delete_session(sid)
            removed.append(sid)
    return removed


async def cleanup_loop(ttl: float = DEFAULT_TTL, interval: float = DEFAULT_INTERVAL):
    """Periodically clean up expired sessions."""
    while True:
        await asyncio.sleep(interval)
        cleanup_expired_sessions(ttl)
