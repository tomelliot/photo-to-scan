from unittest.mock import patch

from app.cleanup import cleanup_expired_sessions
from app.sessions import create_session, get_session, clear_all_sessions


def test_expired_sessions_are_removed():
    clear_all_sessions()
    session = create_session()
    sid = session.id
    # Fake the timestamp to be in the past
    session.last_active = 0

    removed = cleanup_expired_sessions(ttl=10)
    assert sid in removed
    assert get_session(sid) is None
    assert not session.work_dir.exists()


def test_active_sessions_are_preserved():
    clear_all_sessions()
    session = create_session()
    sid = session.id

    removed = cleanup_expired_sessions(ttl=3600)
    assert sid not in removed
    assert get_session(sid) is not None
    assert session.work_dir.exists()
