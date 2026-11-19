import sqlite3
import secrets
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assessments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id),
                topic         TEXT,
                started_at    TEXT NOT NULL,
                completed_at  TEXT,
                overall_score REAL,
                band_label    TEXT
            );

            CREATE TABLE IF NOT EXISTS responses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id   INTEGER NOT NULL REFERENCES assessments(id),
                question_idx    INTEGER NOT NULL,
                question_text   TEXT NOT NULL,
                transcript      TEXT NOT NULL,
                duration        REAL,
                fluency_score          REAL,
                intelligibility_score  REAL,
                language_use_score     REAL,
                organization_score     REAL,
                fluency_reason         TEXT,
                intelligibility_reason TEXT,
                language_use_reason    TEXT,
                organization_reason    TEXT,
                overall_score   REAL,
                band_label      TEXT,
                reasoning       TEXT,
                created_at      TEXT NOT NULL
            );
            """
        )


# ---------------- password helpers ----------------

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()


def create_user(username: str, password: str):
    salt = secrets.token_hex(16)
    pw_hash = hash_password(password, salt)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?,?,?,?)",
            (username, pw_hash, salt, _now()),
        )
        return cur.lastrowid


def get_user_by_name(username: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def verify_user(username: str, password: str):
    user = get_user_by_name(username)
    if not user:
        return None
    if secrets.compare_digest(
        hash_password(password, user["salt"]), user["password_hash"]
    ):
        return user
    return None


# ---------------- auth tokens ----------------

def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at) VALUES (?,?,?)",
            (token, user_id, _now()),
        )
    return token


def user_for_token(token: str):
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT u.* FROM auth_tokens t
               JOIN users u ON u.id = t.user_id
               WHERE t.token = ?""",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def revoke_token(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))


# ---------------- assessments & responses ----------------

def start_assessment(user_id: int, topic: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO assessments (user_id, topic, started_at) VALUES (?,?,?)",
            (user_id, topic, _now()),
        )
        return cur.lastrowid


def save_response(assessment_id: int, question_idx: int, question_text: str,
                  transcript: str, duration: float, result: dict):
    dims = result["dimensions"]
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO responses (
                assessment_id, question_idx, question_text, transcript, duration,
                fluency_score, intelligibility_score, language_use_score, organization_score,
                fluency_reason, intelligibility_reason, language_use_reason, organization_reason,
                overall_score, band_label, reasoning, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                assessment_id, question_idx, question_text, transcript, duration,
                dims["fluency"]["score"], dims["intelligibility"]["score"],
                dims["language_use"]["score"], dims["organization"]["score"],
                dims["fluency"]["reasoning"], dims["intelligibility"]["reasoning"],
                dims["language_use"]["reasoning"], dims["organization"]["reasoning"],
                result["overall_score"], result["band_label"], result["reasoning"],
                _now(),
            ),
        )


def complete_assessment(assessment_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT overall_score FROM responses WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchall()
        if not rows:
            return None
        avg = sum(r["overall_score"] for r in rows) / len(rows)
        band = round(avg * 2) / 2  # keep 0.5 increments
        label = band_label_for(band)
        conn.execute(
            "UPDATE assessments SET completed_at=?, overall_score=?, band_label=? WHERE id=?",
            (_now(), band, label, assessment_id),
        )
        return {"overall_score": band, "band_label": label}


def band_label_for(band: float) -> str:
    from scoring.nodes import cefr_band
    return cefr_band(band)


def get_history(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, topic, started_at, completed_at, overall_score, band_label
               FROM assessments
               WHERE user_id = ? AND completed_at IS NOT NULL
               ORDER BY completed_at ASC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_assessment_detail(user_id: int, assessment_id: int):
    with get_conn() as conn:
        a = conn.execute(
            "SELECT * FROM assessments WHERE id=? AND user_id=?",
            (assessment_id, user_id),
        ).fetchone()
        if not a:
            return None
        resp = conn.execute(
            "SELECT * FROM responses WHERE assessment_id=? ORDER BY question_idx ASC",
            (assessment_id,),
        ).fetchall()
        return {"assessment": dict(a), "responses": [dict(r) for r in resp]}


def get_progress_stats(user_id: int):
    """Aggregate per-dimension averages across all completed responses."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(DISTINCT r.assessment_id)   AS assessments,
                 AVG(r.fluency_score)         AS fluency,
                 AVG(r.intelligibility_score) AS intelligibility,
                 AVG(r.language_use_score)    AS language_use,
                 AVG(r.organization_score)    AS organization,
                 AVG(r.overall_score)         AS overall
               FROM responses r
               JOIN assessments a ON a.id = r.assessment_id
               WHERE a.user_id = ? AND a.completed_at IS NOT NULL""",
            (user_id,),
        ).fetchone()
        return dict(row) if row else {}
