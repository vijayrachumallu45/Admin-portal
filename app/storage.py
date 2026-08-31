"""SQLite document store for operational domains."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DATABASE_PATH


def db_path() -> Path:
    override = os.environ.get("NEXUSOPS_DB", "").strip()
    if override:
        return Path(override)
    return DATABASE_PATH


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


class Store:
    def __init__(self) -> None:
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS domain_rows (
                    domain TEXT NOT NULL,
                    id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (domain, id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operators (
                    email TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def new_id(self, domain: str) -> str:
        return f"{domain[:3]}-{uuid.uuid4().hex[:10]}"

    def list_domain(self, domain: str) -> list[dict[str, Any]]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM domain_rows WHERE domain = ? ORDER BY updated_at DESC",
                (domain,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get_domain(self, domain: str, record_id: str) -> dict[str, Any] | None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT payload FROM domain_rows WHERE domain = ? AND id = ?",
                (domain, record_id),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def upsert_domain(self, domain: str, payload: dict[str, Any]) -> None:
        record_id = str(payload["id"])
        stamp = payload.get("updated_at") or datetime.utcnow().isoformat() + "Z"
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO domain_rows(domain, id, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain, id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (domain, record_id, json.dumps(payload), stamp),
            )
            conn.commit()

    def delete_domain(self, domain: str, record_id: str) -> bool:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM domain_rows WHERE domain = ? AND id = ?",
                (domain, record_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def append_audit(self, action: str, domain: str, record_id: str) -> None:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(id, action, domain, record_id, at) VALUES (?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    action,
                    domain,
                    record_id,
                    datetime.utcnow().isoformat() + "Z",
                ),
            )
            conn.commit()

    def recent_audit(self, limit: int = 12) -> list[dict[str, Any]]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT action, domain, record_id, at FROM audit_log ORDER BY at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_operator(self, email: str) -> dict[str, Any] | None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT email, name, password_hash, role FROM operators WHERE email = ?",
                (email.lower(),),
            ).fetchone()
        return dict(row) if row else None

    def upsert_operator(self, email: str, name: str, password_hash: str, role: str) -> None:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO operators(email, name, password_hash, role)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name = excluded.name,
                    password_hash = excluded.password_hash,
                    role = excluded.role
                """,
                (email.lower(), name, password_hash, role),
            )
            conn.commit()

    def count_domains(self) -> dict[str, int]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT domain, COUNT(*) AS n FROM domain_rows GROUP BY domain"
            ).fetchall()
        return {row["domain"]: int(row["n"]) for row in rows}


store = Store()
