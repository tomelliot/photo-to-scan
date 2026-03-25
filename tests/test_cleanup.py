import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from app.cleanup import cleanup_expired_sessions
from app.sessions import (
    create_session,
    get_session,
    clear_all_sessions,
    purge_expired_archives,
    archive_session,
    SESSION_META_FILE,
)


def test_expired_sessions_are_archived():
    clear_all_sessions()
    session = create_session()
    sid = session.id
    work_dir = session.work_dir
    # Fake the timestamp to be in the past
    session.last_active = 0

    removed = cleanup_expired_sessions(ttl=10)
    assert sid in removed
    assert get_session(sid) is None
    # Work dir should still exist (archived, not deleted)
    assert work_dir.exists()
    assert (work_dir / SESSION_META_FILE).exists()

    # Verify metadata content
    meta = json.loads((work_dir / SESSION_META_FILE).read_text())
    assert meta["reason"] == "expired"
    assert "archived_at" in meta
    assert "created_at" in meta
    assert meta["page_count"] == 0


def test_active_sessions_are_preserved():
    clear_all_sessions()
    session = create_session()
    sid = session.id

    removed = cleanup_expired_sessions(ttl=3600)
    assert sid not in removed
    assert get_session(sid) is not None
    assert session.work_dir.exists()


def test_purge_removes_archives_past_retention(tmp_path):
    """Archived sessions older than retention_days are purged."""
    old_dir = tmp_path / "old-session"
    old_dir.mkdir()
    old_meta = {
        "created_at": "2020-01-01T00:00:00+00:00",
        "archived_at": "2020-01-01T01:00:00+00:00",
        "reason": "submitted",
        "page_count": 2,
    }
    (old_dir / SESSION_META_FILE).write_text(json.dumps(old_meta))

    recent_dir = tmp_path / "recent-session"
    recent_dir.mkdir()
    now = datetime.now(timezone.utc)
    recent_meta = {
        "created_at": now.isoformat(),
        "archived_at": now.isoformat(),
        "reason": "submitted",
        "page_count": 1,
    }
    (recent_dir / SESSION_META_FILE).write_text(json.dumps(recent_meta))

    with patch("app.sessions.get_settings") as mock_settings:
        mock_settings.return_value.work_dir = str(tmp_path)
        mock_settings.return_value.retention_days = 7
        purge_expired_archives()

    assert not old_dir.exists()
    assert recent_dir.exists()


def test_purge_handles_malformed_metadata(tmp_path):
    """Dirs with malformed .session_meta.json are purged immediately."""
    bad_dir = tmp_path / "bad-meta"
    bad_dir.mkdir()
    (bad_dir / SESSION_META_FILE).write_text("not json")

    with patch("app.sessions.get_settings") as mock_settings:
        mock_settings.return_value.work_dir = str(tmp_path)
        mock_settings.return_value.retention_days = 7
        purge_expired_archives()

    assert not bad_dir.exists()


def test_archive_then_purge_lifecycle(tmp_path):
    """Full lifecycle: create -> archive -> retain -> purge."""
    clear_all_sessions()

    with patch("app.sessions.get_settings") as mock_settings:
        mock_settings.return_value.work_dir = str(tmp_path)
        mock_settings.return_value.retention_days = 7

        # Create and archive a session
        session = create_session()
        sid = session.id
        work_dir = session.work_dir

        archive_session(sid, reason="submitted")

        # Session removed from memory but files retained
        assert get_session(sid) is None
        assert work_dir.exists()
        assert (work_dir / SESSION_META_FILE).exists()

        # Purge with retention_days=7 should keep it (just archived)
        purge_expired_archives(retention_days=7)
        assert work_dir.exists()

        # Backdate the archive to make it expire
        meta = json.loads((work_dir / SESSION_META_FILE).read_text())
        old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        meta["archived_at"] = old_date
        (work_dir / SESSION_META_FILE).write_text(json.dumps(meta))

        # Now purge should remove it
        purge_expired_archives(retention_days=7)
        assert not work_dir.exists()
