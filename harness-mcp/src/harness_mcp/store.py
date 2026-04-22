"""Session store: discovers and loads agent_logs/* directories.

A "session" is any directory matching the layout the harness CLI produces:
    <root>/<session_id>/agent_logs/{trace.md, tool_calls.json, diff_summary.md, session_meta.json}

Or the root *itself* may be a single agent_logs/ directory, in which case the
session id is the parent folder's name.

The store keeps a small in-memory index. Calls to refresh() rescan from disk
so Claude (or the dashboard) can pick up new runs without restarting.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from harness.parser import load_logs
from harness.scorer import score as score_logs
from harness.schemas import HarnessInput, HarnessResult


REQUIRED_FILES = ("trace.md", "tool_calls.json", "diff_summary.md")


@dataclass
class Session:
    id: str
    logs_dir: Path
    project: str = ""
    model: str = ""
    date: str = ""

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "logs_dir": str(self.logs_dir),
            "project": self.project,
            "model": self.model,
            "date": self.date,
        }


@dataclass
class SessionStore:
    root: Path
    _sessions: dict[str, Session] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.refresh()

    # --- discovery -------------------------------------------------------

    def _discover(self) -> dict[str, Session]:
        found: dict[str, Session] = {}
        if not self.root.exists():
            return found

        candidates: list[Path] = []
        if self._is_logs_dir(self.root):
            candidates.append(self.root)
        for child in sorted(self.root.iterdir()):
            if not child.is_dir():
                continue
            if self._is_logs_dir(child):
                candidates.append(child)
            inner = child / "agent_logs"
            if self._is_logs_dir(inner):
                candidates.append(inner)

        for logs_dir in candidates:
            session_id = self._session_id_for(logs_dir)
            if session_id in found:
                continue
            sess = Session(id=session_id, logs_dir=logs_dir)
            self._fill_meta(sess)
            found[session_id] = sess
        return found

    @staticmethod
    def _is_logs_dir(path: Path) -> bool:
        return path.is_dir() and all((path / f).exists() for f in REQUIRED_FILES)

    def _session_id_for(self, logs_dir: Path) -> str:
        if logs_dir.name == "agent_logs":
            return logs_dir.parent.name or "root"
        return logs_dir.name

    def _fill_meta(self, sess: Session) -> None:
        meta_path = sess.logs_dir / "session_meta.json"
        if not meta_path.exists():
            return
        try:
            import json
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            sess.project = str(data.get("project", "") or "")
            sess.model = str(data.get("model", "") or "")
            sess.date = str(data.get("date", "") or "")
        except Exception:
            pass

    # --- public API ------------------------------------------------------

    def refresh(self) -> list[Session]:
        """Rescan disk. Returns the new session list."""
        with self._lock:
            self._sessions = self._discover()
            return list(self._sessions.values())

    def list_sessions(self) -> list[Session]:
        with self._lock:
            return list(self._sessions.values())

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            return self._sessions.get(session_id)

    def load(self, session_id: str) -> HarnessInput:
        sess = self._require(session_id)
        return load_logs(sess.logs_dir)

    def score(self, session_id: str) -> HarnessResult:
        return score_logs(self.load(session_id))

    def _require(self, session_id: str) -> Session:
        sess = self.get(session_id)
        if sess is None:
            raise KeyError(f"Unknown session: {session_id}. Try refresh().")
        return sess
