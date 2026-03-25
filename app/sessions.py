"""In-memory session state for document pages."""

import json
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from time import time

from app.config import get_settings

logger = logging.getLogger(__name__)

SESSION_META_FILE = ".session_meta.json"


@dataclass
class PageEntry:
    id: str
    original: Path
    processed: Path | None = None
    status: str = "pending"  # "pending" | "done" | "error"
    rotation: int = 0  # cumulative CW rotation in degrees (0, 90, 180, 270)


@dataclass
class Session:
    id: str
    work_dir: Path
    pages: list[PageEntry] = field(default_factory=list)
    created_at: float = field(default_factory=time)
    last_active: float = field(default_factory=time)
    submitted: bool = False

    def touch(self):
        self.last_active = time()


# Global session store: session_id -> Session
_sessions: dict[str, Session] = {}

SESSION_COOKIE = "docprep_session"


def get_or_create_session(session_id: str | None) -> Session:
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session.touch()
        return session
    return create_session()


def create_session() -> Session:
    sid = uuid.uuid4().hex
    settings = get_settings()
    work_dir = Path(settings.work_dir) / sid
    work_dir.mkdir(parents=True, exist_ok=True)
    session = Session(id=sid, work_dir=work_dir)
    _sessions[sid] = session
    logger.info("Session created: %s", sid)
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def delete_session(session_id: str):
    session = _sessions.pop(session_id, None)
    if session and session.work_dir.exists():
        shutil.rmtree(session.work_dir)


def get_all_sessions() -> dict[str, Session]:
    return _sessions


def archive_session(session_id: str, reason: str = "submitted"):
    """Archive a session: write metadata file and remove from in-memory store."""
    session = _sessions.pop(session_id, None)
    if not session:
        return

    now = datetime.now(timezone.utc)
    meta = {
        "created_at": datetime.fromtimestamp(session.created_at, tz=timezone.utc).isoformat(),
        "archived_at": now.isoformat(),
        "reason": reason,
        "page_count": len(session.pages),
    }
    meta_path = session.work_dir / SESSION_META_FILE
    meta_path.write_text(json.dumps(meta, indent=2))

    # Remove legacy .submitted marker if present
    submitted_marker = session.work_dir / ".submitted"
    if submitted_marker.exists():
        submitted_marker.unlink()

    logger.info(
        "Session archived: %s reason=%s pages=%d",
        session_id,
        reason,
        len(session.pages),
    )


def mark_session_submitted(session_id: str):
    """Mark a session as submitted in memory (for double-submit guard)."""
    session = _sessions.get(session_id)
    if session:
        session.submitted = True


def purge_expired_archives(retention_days: int | None = None):
    """Scan work_dir for archived session dirs past retention and delete them.

    Also handles migration of legacy .submitted marker dirs.
    """
    settings = get_settings()
    if retention_days is None:
        retention_days = settings.retention_days
    base = Path(settings.work_dir)
    if not base.exists():
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    for child in base.iterdir():
        if not child.is_dir():
            continue

        meta_path = child / SESSION_META_FILE
        submitted_marker = child / ".submitted"

        if meta_path.exists():
            # Archived session — check if past retention
            try:
                meta = json.loads(meta_path.read_text())
                archived_at = datetime.fromisoformat(meta["archived_at"])
                if archived_at < cutoff:
                    shutil.rmtree(child)
                    logger.info("Session purged: %s (archived_at=%s)", child.name, meta["archived_at"])
            except (json.JSONDecodeError, KeyError, ValueError):
                # Malformed metadata — purge immediately
                shutil.rmtree(child)
                logger.warning("Session purged (malformed metadata): %s", child.name)

        elif submitted_marker.exists():
            # Legacy .submitted marker — migrate: archive now, purge in retention_days
            meta = {
                "created_at": now.isoformat(),
                "archived_at": now.isoformat(),
                "reason": "submitted",
                "page_count": 0,
            }
            meta_path.write_text(json.dumps(meta, indent=2))
            submitted_marker.unlink()
            logger.info("Legacy session migrated: %s", child.name)


def cleanup_submitted_sessions():
    """Startup cleanup — now retention-aware."""
    purge_expired_archives()


def clear_all_sessions():
    """For testing only."""
    for sid in list(_sessions):
        delete_session(sid)
