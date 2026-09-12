import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def now():
    return datetime.now(UTC).isoformat()


class Store:
    """Short transactions and a unique object key provide durable, correctable memory."""

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, at TEXT, kind TEXT, ref TEXT, body TEXT)"
            )

    @contextmanager
    def connection(self):
        with sqlite3.connect(self.path, timeout=20) as db:
            db.row_factory = sqlite3.Row
            yield db

    def put(self, kind, id, value):
        with self.connection() as db:
            db.execute(
                "INSERT INTO objects VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body",
                (kind, id, json.dumps(value)),
            )
        return value

    def get(self, kind, id):
        with self.connection() as db:
            row = db.execute("SELECT body FROM objects WHERE kind=? AND id=?", (kind, id)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, kind):
        with self.connection() as db:
            rows = db.execute("SELECT body FROM objects WHERE kind=? ORDER BY rowid", (kind,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, kind, id):
        with self.connection() as db:
            db.execute("DELETE FROM objects WHERE kind=? AND id=?", (kind, id))

    def log(self, kind, ref, detail):
        with self.connection() as db:
            db.execute(
                "INSERT INTO audit(at,kind,ref,body) VALUES (?,?,?,?)", (now(), kind, ref, json.dumps(detail))
            )

    def audit(self):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT 200").fetchall()
        return [{**dict(r), "body": json.loads(r["body"])} for r in rows]

    def claim(self, kind, id, value):
        with self.connection() as db:
            return (
                db.execute(
                    "INSERT OR IGNORE INTO objects VALUES (?,?,?)", (kind, id, json.dumps(value))
                ).rowcount
                == 1
            )
