import os
import sqlite3

# The database is one file, stored next to this script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name: row["role"]
    return conn


def init_db():
    """Create the tables if they don't exist yet. Safe to call on every rerun."""
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
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
    conn.commit()
    conn.close()


def create_conversation(title="New chat"):
    """Create a new conversation and return its id."""
    conn = connect()
    cursor = conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    return conversation_id


def get_latest_conversation_id():
    """Return the id of the newest conversation, or None if there are none."""
    conn = connect()
    row = conn.execute("SELECT id FROM conversations ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["id"] if row else None


def list_conversations():
    """Return all conversations (id and title), newest first."""
    conn = connect()
    rows = conn.execute("SELECT id, title FROM conversations ORDER BY id DESC").fetchall()
    conn.close()
    return [{"id": row["id"], "title": row["title"]} for row in rows]


def set_title(conversation_id, title):
    """Rename a conversation."""
    conn = connect()
    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
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
