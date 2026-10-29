from __future__ import annotations
import json, sqlite3, threading, time
from pathlib import Path
from typing import Any

from ..security.aead import Sealer
from ..guard.vocabulary import check_output
from .migrations import MIGRATIONS, LATEST


class MigrationError(RuntimeError):
    pass


class DB:
    def __init__(self, path: str | Path, key: bytes):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL") if self.path != ":memory:" else None
        self.sealer = Sealer(key)
        self.lock = threading.RLock()
        self.migrate()

    @property
    def version(self) -> int:
        return self.conn.execute("PRAGMA user_version").fetchone()[0]

    def migrate(self, target: int = LATEST) -> int:
        cur = self.version
        if cur > LATEST:
            raise MigrationError(f"DB schema v{cur} is newer than this build (v{LATEST}); refusing to touch it")
        for v, sql in MIGRATIONS:
            if cur < v <= target:
                with self.lock:
                    try:
                        self.conn.execute("BEGIN")
                        for stmt in filter(str.strip, sql.split(";")):
                            self.conn.execute(stmt)
                        self.conn.execute(f"PRAGMA user_version={v}")
                        self.conn.execute("COMMIT")
                    except Exception as e:
                        self.conn.execute("ROLLBACK")
                        raise MigrationError(f"migration {v} failed: {e}") from e
        return self.version

    def execute(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, args)

    def commit(self) -> None:
        pass  # autocommit mode

    def has_table(self, t: str) -> bool:
        return self.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone() is not None

    def has_column(self, t: str, c: str) -> bool:
        return any(r[1] == c for r in self.execute(f"PRAGMA table_info({t})"))

    def seal_json(self, obj: Any, aad: bytes = b"") -> bytes:
        check_output(obj)
        return self.sealer.seal(json.dumps(obj, sort_keys=True).encode(), aad)

    def open_json(self, blob: bytes, aad: bytes = b"") -> Any:
        return json.loads(self.sealer.open(blob, aad))

    def audit(self, kind: str, detail: dict) -> None:
        self.execute("INSERT INTO audit_log(t_wall,kind,detail) VALUES(?,?,?)", (time.time(), kind, json.dumps(detail)))

    def close(self) -> None:
        self.conn.close()
