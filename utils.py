import os
import sqlite3
from threading import Lock
from datetime import datetime

DB_PATH = os.getenv("SQLITE_DB_PATH", "senticord.db")
_conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
_lock   = Lock()
_cursor = _conn.cursor()

# ─── pending_captchas ──────────────────────────────────────────────────
_cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_captchas (
  member_id TEXT PRIMARY KEY,
  guild_id  TEXT,
  code      TEXT,
  attempts  INTEGER,
  created   TEXT
);
""")

def get_pending(member_id: str):
    _cursor.execute(
        "SELECT guild_id,code,attempts,created FROM pending_captchas WHERE member_id=?",
        (member_id,)
    )
    row = _cursor.fetchone()
    if not row:
        return None
    guild_id, code, attempts, created = row
    return {
        "guild_id": guild_id,
        "code":      code,
        "attempts":  attempts,
        "created":   datetime.fromisoformat(created)
    }

def set_pending(member_id: str, guild_id: str, code: str):
    now = datetime.utcnow().isoformat()
    with _lock:
        _cursor.execute("""
            INSERT OR REPLACE INTO pending_captchas(member_id,guild_id,code,attempts,created)
            VALUES(?,?,?,?,?)
        """, (member_id, guild_id, code, 0, now))
        _conn.commit()

def update_attempts(member_id: str, attempts: int):
    with _lock:
        _cursor.execute(
            "UPDATE pending_captchas SET attempts=? WHERE member_id=?",
            (attempts, member_id)
        )
        _conn.commit()

def delete_pending(member_id: str):
    with _lock:
        _cursor.execute(
            "DELETE FROM pending_captchas WHERE member_id=?",
            (member_id,)
        )
        _conn.commit()

# ─── guild_settings ────────────────────────────────────────────────────
_cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id    TEXT PRIMARY KEY,
  admin_role  TEXT,
  log_channel TEXT
);
""")
_conn.commit()

def get_settings(guild_id: str):
    _cursor.execute(
        "SELECT admin_role, log_channel FROM guild_settings WHERE guild_id=?",
        (guild_id,)
    )
    row = _cursor.fetchone()
    return {"admin_role": row[0], "log_channel": row[1]} if row else {}

def set_settings(guild_id: str, admin_role: str=None, log_channel: str=None):
    existing = get_settings(guild_id)
    ar = admin_role  if admin_role  is not None else existing.get("admin_role")
    lc = log_channel if log_channel is not None else existing.get("log_channel")
    with _lock:
        if existing:
            _cursor.execute(
                "UPDATE guild_settings SET admin_role=?, log_channel=? WHERE guild_id=?",
                (ar, lc, guild_id)
            )
        else:
            _cursor.execute(
                "INSERT INTO guild_settings(guild_id,admin_role,log_channel) VALUES(?,?,?)",
                (guild_id, ar, lc)
            )
        _conn.commit()
