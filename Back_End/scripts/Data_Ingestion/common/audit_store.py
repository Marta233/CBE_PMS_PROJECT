"""
audit_store.py - the single writer of the knowledge base, with a full trail.

Files it owns (all next to knowledge_base.json unless noted):

    knowledge_base.json      ACTIVE documents only. Retrieval reads this; its shape is unchanged.
    knowledge_archive.jsonl  every document that was REPLACED, one JSON object per line,
                             stamped with superseded_by / superseded_at. Append-only.
    ingestion_log.jsonl      one line per upload attempt (success, dry run, rejection, virus,
                             failure): who, when, file, hash, scan, scope, counts, replaced batches.
                             Append-only.
    uploads/archive/<batch>/ the original uploaded file, so any batch can be re-ingested.
    quarantine/              files that failed the virus scan.

Nothing here ever deletes history. Replacement = move to archive, never erase.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

try:                       # POSIX
    import fcntl           # type: ignore
except ImportError:        # Windows
    fcntl = None
try:
    import msvcrt          # type: ignore
except ImportError:
    msvcrt = None


# ------------------------------------------------------------------ JSON
class _SafeEncoder(json.JSONEncoder):
    """Handles numpy / pandas values and NaN so json.dumps never fails on loader output."""

    def default(self, obj: Any) -> Any:
        try:
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return None if math.isnan(float(obj)) else float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
        except ImportError:
            pass
        return str(obj)

    def iterencode(self, obj: Any, _one_shot: bool = False):
        return super().iterencode(_sanitise(obj), _one_shot)


def _sanitise(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise(v) for v in obj]
    return obj


def safe_dumps(data: Any, indent: Optional[int] = 2) -> str:
    return json.dumps(data, cls=_SafeEncoder, indent=indent, ensure_ascii=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


# ------------------------------------------------------------------ lock
_THREAD_LOCK = threading.RLock()


class FileLock:
    """
    Cross-process exclusive lock (fcntl on Linux/macOS, msvcrt on Windows) plus an
    in-process RLock. Prevents two uploads from reading the same knowledge base and
    the second one silently overwriting the first.
    """

    def __init__(self, path: Path, timeout: float = 120.0):
        self.path = Path(path)
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        _THREAD_LOCK.acquire()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+b")
        deadline = time.time() + self.timeout
        while True:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif msvcrt is not None:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.time() > deadline:
                    self._fh.close()
                    _THREAD_LOCK.release()
                    raise TimeoutError("Another upload is writing the knowledge base; try again.")
                time.sleep(0.1)

    def __exit__(self, *exc):
        try:
            if fcntl is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._fh.close()
            _THREAD_LOCK.release()


# ------------------------------------------------------------------ store
class KnowledgeBaseUnreadable(Exception):
    pass


class AuditStore:
    def __init__(self, docs_dir: Path, uploads_dir: Path, quarantine_dir: Optional[Path] = None,
                 kb_file: Optional[Path] = None):
        self.docs_dir = Path(docs_dir)
        self.kb_file = Path(kb_file) if kb_file else self.docs_dir / "knowledge_base.json"
        self.archive_file = self.docs_dir / "knowledge_archive.jsonl"
        self.log_file = self.docs_dir / "ingestion_log.jsonl"
        self.originals_dir = Path(uploads_dir) / "archive"
        self.quarantine_dir = Path(quarantine_dir) if quarantine_dir else Path(uploads_dir).parent / "quarantine"
        self.lock_file = self.docs_dir / ".knowledge_base.lock"
        for d in (self.docs_dir, self.originals_dir, self.quarantine_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---- locking -------------------------------------------------------
    @contextmanager
    def writer(self, timeout: float = 120.0) -> Iterator[None]:
        with FileLock(self.lock_file, timeout):
            yield

    # ---- knowledge base ------------------------------------------------
    def read_kb(self) -> list:
        """Active documents. Refuses (raises) rather than returning [] for an unreadable file,
        because writing back an empty list would erase the knowledge base."""
        if not self.kb_file.exists() or self.kb_file.stat().st_size == 0:
            return []
        try:
            data = json.loads(self.kb_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("top-level JSON is not a list")
            return data
        except Exception as exc:
            raise KnowledgeBaseUnreadable(str(exc))

    def write_kb(self, docs: list) -> None:
        """Write fully to a temp file, keep one .bak of the previous file, then swap in."""
        tmp = self.kb_file.with_suffix(".json.tmp")
        tmp.write_text(safe_dumps(docs), encoding="utf-8")
        if self.kb_file.exists():
            shutil.copy2(self.kb_file, self.kb_file.with_suffix(".json.bak"))
        os.replace(tmp, self.kb_file)

    # ---- append-only logs ---------------------------------------------
    def _append(self, path: Path, records: Iterable[dict]) -> int:
        n = 0
        with open(path, "a", encoding="utf-8") as fh:
            for r in records:
                fh.write(safe_dumps(r, indent=None) + "\n")
                n += 1
            fh.flush()
            os.fsync(fh.fileno())
        return n

    def archive_superseded(self, docs: list, superseded_by: str, when: str) -> int:
        stamped = []
        for d in docs:
            meta = dict(d.get("metadata", {}))
            meta["status"] = "superseded"
            meta["superseded_by"] = superseded_by
            meta["superseded_at"] = when
            stamped.append({"text": d.get("text", ""), "metadata": meta})
        return self._append(self.archive_file, stamped)

    def log_event(self, record: dict) -> None:
        record = {"logged_at": utc_now(), **record}
        self._append(self.log_file, [record])

    def read_log(self, limit: int = 50) -> list:
        if not self.log_file.exists():
            return []
        lines = self.log_file.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(out))

    def find_by_hash(self, sha256: str, doc_type: str) -> Optional[dict]:
        """Most recent successful ingest of exactly this file, if any."""
        for rec in self.read_log(limit=500):
            if rec.get("sha256") == sha256 and rec.get("doc_type") == doc_type \
                    and rec.get("outcome") == "success":
                return rec
        return None

    # ---- files ---------------------------------------------------------
    def archive_original(self, batch_id: str, filename: str, data: bytes) -> Path:
        d = self.originals_dir / batch_id
        d.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "._-() " else "_" for c in (filename or "upload"))
        p = d / safe_name
        p.write_bytes(data)
        return p

    def quarantine(self, batch_id: str, filename: str, data: bytes, reason: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in (filename or "upload"))
        p = self.quarantine_dir / f"{batch_id}__{safe_name}.quarantined"
        p.write_bytes(data)
        (self.quarantine_dir / f"{batch_id}.reason.txt").write_text(reason, encoding="utf-8")
        return p