import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Optional, List, Tuple

# Database file path - use environment variable or default
DB_PATH = os.environ.get("DB_PATH", "data/bot.db")


def get_db_path() -> str:
    """Get database path and ensure directory exists."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """Initialize database with required tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by TEXT DEFAULT 'migration'
            )
        """)

        # Download stats table (optional, for future use)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_stats (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                platform TEXT,
                quality TEXT,
                file_size INTEGER,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Access requests from unknown users, approved/rejected by the admin
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_requests (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                decided_at TIMESTAMP
            )
        """)

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)
        """)

        logging.info(f"Database initialized at {get_db_path()}")


def add_user(user_id: int, username: Optional[str] = None, added_by: str = "admin") -> bool:
    """Add a user to the allowed list. Returns True if added, False if already exists."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username, added_by) VALUES (?, ?, ?)",
                (user_id, username, added_by)
            )
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error adding user {user_id}: {e}")
        return False


def remove_user(user_id: int) -> bool:
    """Remove a user from the allowed list."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error removing user {user_id}: {e}")
        return False


def is_user_allowed(user_id: int) -> bool:
    """Check if a user is in the allowed list."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"Error checking user {user_id}: {e}")
        return False


def get_all_users() -> List[Tuple[int, Optional[str]]]:
    """Get all allowed users."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM users ORDER BY added_at")
            return [(row["user_id"], row["username"]) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error getting users: {e}")
        return []


def get_user_count() -> int:
    """Get total number of allowed users."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            row = cursor.fetchone()
            return row["count"] if row else 0
    except Exception as e:
        logging.error(f"Error counting users: {e}")
        return 0


def get_access_request_status(user_id: int) -> Optional[str]:
    """Return 'pending' / 'approved' / 'rejected', or None if the user never asked."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM access_requests WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row["status"] if row else None
    except Exception as e:
        logging.error(f"Error reading access request {user_id}: {e}")
        return None


def create_access_request(user_id: int, username: Optional[str], full_name: Optional[str]) -> bool:
    """Create a pending request. Returns False if the user already has one (any status)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO access_requests (user_id, username, full_name) VALUES (?, ?, ?)",
                (user_id, username, full_name)
            )
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error creating access request {user_id}: {e}")
        return False


def delete_access_request(user_id: int) -> bool:
    """Drop a request so the user can ask again."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM access_requests WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error deleting access request {user_id}: {e}")
        return False


def decide_access_request(user_id: int, status: str) -> Optional[dict]:
    """Move a pending request to 'approved'/'rejected'.

    Returns the request (username, full_name) or None if there was no pending
    request, so a second click on the admin buttons is a no-op.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE access_requests SET status = ?, decided_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND status = 'pending'""",
                (status, user_id)
            )
            if cursor.rowcount == 0:
                return None
            cursor.execute(
                "SELECT username, full_name FROM access_requests WHERE user_id = ?", (user_id,)
            )
            return dict(cursor.fetchone())
    except Exception as e:
        logging.error(f"Error deciding access request {user_id}: {e}")
        return None


def log_download(user_id: int, url: str, platform: str, quality: str, file_size: int = 0):
    """Log a download for statistics."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO download_stats
                   (user_id, url, platform, quality, file_size)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, url, platform, quality, file_size)
            )
    except Exception as e:
        logging.error(f"Error logging download: {e}")


def migrate_from_file(file_path: str = "allowed_users.txt") -> int:
    """Migrate users from allowed_users.txt to SQLite. Returns count of migrated users."""
    if not os.path.exists(file_path):
        logging.info(f"No {file_path} found, skipping migration")
        return 0

    migrated = 0
    try:
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse line: "123456789 # username"
                    parts = line.split('#')
                    user_id_str = parts[0].strip()
                    username = parts[1].strip() if len(parts) > 1 else None

                    try:
                        user_id = int(user_id_str)
                        if add_user(user_id, username, added_by="migration"):
                            migrated += 1
                            logging.info(f"Migrated user {user_id} ({username})")
                    except ValueError:
                        logging.warning(f"Invalid user ID in migration: {user_id_str}")

        logging.info(f"Migration complete: {migrated} users added")
        return migrated
    except Exception as e:
        logging.error(f"Migration error: {e}")
        return migrated


# Initialize database on module import
init_db()
