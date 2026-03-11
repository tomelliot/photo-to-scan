"""In-memory session state for document pages."""

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from time import time

from app.config import get_settings


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
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def delete_session(session_id: str):
    session = _sessions.pop(session_id, None)
    if session and session.work_dir.exists():
        shutil.rmtree(session.work_dir)


def get_all_sessions() -> dict[str, Session]:
    return _sessions


def clear_all_sessions():
    """For testing only."""
    for sid in list(_sessions):
        delete_session(sid)
