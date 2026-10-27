"""Append-only local import revisions; never merge financial snapshots."""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


def atomic_write(path: Path, data: bytes, replace=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ca-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ValueError(f"El archivo archivado no coincide: {path}") from None
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_import(db_path: Path, source: Path, snapshot: dict, report: dict) -> tuple[int, bool]:
    if report["status"] not in ("reconciled", "review_required"):
        raise ValueError("Una conciliación invalid no se guarda como cartera aceptada.")
    data = Path(source).read_bytes()
    source_hash = sha256(data).hexdigest()
    if source_hash != snapshot["source_sha256"]:
        raise ValueError("El hash del archivo cambió desde su lectura; vuelva a importar.")
    encoded_snapshot = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False)
    encoded_report = json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False)
    db_path = Path(db_path)
    source_file = f"sources/{source_hash}.xlsx"
    atomic_write(db_path.parent / source_file, data, replace=False)
    connection = sqlite3.connect(db_path)
    try:
        with connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY,
                source_sha256 TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                source_file TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                report_json TEXT NOT NULL,
                UNIQUE(source_sha256, schema_version)
            )""")
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT id FROM imports WHERE source_sha256=? AND schema_version=?",
                (source_hash, snapshot["schema_version"])).fetchone()
            if previous:
                return previous[0], False
            cursor = connection.execute(
                """INSERT INTO imports(source_sha256, schema_version, source_file, imported_at,
                    snapshot_json, report_json) VALUES (?, ?, ?, ?, ?, ?)""",
                (source_hash, snapshot["schema_version"], source_file, datetime.now(timezone.utc).isoformat(),
                 encoded_snapshot, encoded_report))
            return cursor.lastrowid, True
    finally:
        connection.close()


def load_import(db_path: Path, revision: int) -> tuple[dict, dict]:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("SELECT snapshot_json, report_json FROM imports WHERE id=?", (revision,)).fetchone()
        if row is None:
            raise ValueError(f"No existe la revisión {revision}")
        return json.loads(row[0]), json.loads(row[1])
    finally:
        connection.close()
