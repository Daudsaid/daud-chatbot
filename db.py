import os
import sqlite3
from datetime import datetime, timezone

# The database is one file, stored next to this script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name: row["role"]
    return conn


def add_column_if_missing(conn, table, column, definition):
    """Migration helper: add a column to an existing table if it isn't there yet.

    CREATE TABLE IF NOT EXISTS won't add new columns to an old table, so
    databases created by earlier versions of the app need this.
    (Table and column names can't use ? placeholders, so they're put in the
    SQL directly. That's safe here because they're our own fixed strings.)
    """
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    """Create the tables if they don't exist yet. Safe to call on every rerun."""
    conn = connect()
    # user_id says who a chat belongs to: "owner", or a visitor's random id
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'owner',
            title TEXT NOT NULL,
            system_prompt TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    add_column_if_missing(conn, "conversations", "system_prompt", "TEXT NOT NULL DEFAULT ''")
    # Chats from before visitors existed belong to the owner
    add_column_if_missing(conn, "conversations", "user_id", "TEXT NOT NULL DEFAULT 'owner'")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # One row per day: how many free demo questions all visitors used that day
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_usage (
            day TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def create_conversation(user_id, title="New chat"):
    """Create a new conversation for this user and return its id."""
    conn = connect()
    cursor = conn.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)", (user_id, title)
    )
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    return conversation_id


def get_latest_conversation_id(user_id):
    """Return the id of this user's newest conversation, or None if they have none."""
    conn = connect()
    row = conn.execute(
        "SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def list_conversations(user_id):
    """Return this user's conversations (id and title), newest first."""
    conn = connect()
    rows = conn.execute(
        "SELECT id, title FROM conversations WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"id": row["id"], "title": row["title"]} for row in rows]


def make_title(text):
    """Turn a message into a short chat title (max 40 characters)."""
    return text if len(text) <= 40 else text[:40] + "..."


def set_title(conversation_id, title):
    """Rename a conversation."""
    conn = connect()
    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
    conn.commit()
    conn.close()


def get_system_prompt(conversation_id):
    """Return a conversation's system prompt ('' means none)."""
    conn = connect()
    row = conn.execute(
        "SELECT system_prompt FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    conn.close()
    return row["system_prompt"] if row else ""


def set_system_prompt(conversation_id, system_prompt):
    """Save a conversation's system prompt."""
    conn = connect()
    conn.execute(
        "UPDATE conversations SET system_prompt = ? WHERE id = ?",
        (system_prompt, conversation_id),
    )
    conn.commit()
    conn.close()


def delete_conversation(conversation_id):
    """Delete a conversation and all of its messages."""
    conn = connect()
    # Delete the messages first so none are left pointing at a missing chat
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()


def add_message(conversation_id, role, content):
    """Save one message to a conversation."""
    conn = connect()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, role, content),
    )
    conn.commit()
    conn.close()


def get_messages(conversation_id):
    """Load a conversation's messages, oldest first, in the format the API expects."""
    conn = connect()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def today():
    """Today's date in UTC, e.g. '2026-10-20'. The daily limit resets at midnight UTC."""
    return datetime.now(timezone.utc).date().isoformat()


def get_daily_count():
    """How many free demo questions all visitors have used today."""
    conn = connect()
    row = conn.execute("SELECT count FROM daily_usage WHERE day = ?", (today(),)).fetchone()
    conn.close()
    return row["count"] if row else 0


def increment_daily_count():
    """Add one to today's counter, in a single statement (an "upsert"):
    insert today's row with count 1, or if it already exists, add 1 to it."""
    conn = connect()
    conn.execute(
        """
        INSERT INTO daily_usage (day, count) VALUES (?, 1)
        ON CONFLICT(day) DO UPDATE SET count = count + 1
        """,
        (today(),),
    )
    conn.commit()
    conn.close()
