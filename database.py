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

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stats_user_time ON download_stats(user_id, downloaded_at)
        """)

        # Per-user daily limit override (NULL = default from config)
        columns = {row["name"] for row in cursor.execute("PRAGMA table_info(users)")}
        if "daily_limit" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN daily_limit INTEGER")

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


def count_downloads_since(user_id: int, hours: int = 24) -> int:
    """Count successful downloads of a user in the last `hours` hours."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COUNT(*) AS count FROM download_stats
                   WHERE user_id = ? AND downloaded_at >= datetime('now', ?)""",
                (user_id, f"-{int(hours)} hours")
            )
            row = cursor.fetchone()
            return row["count"] if row else 0
    except Exception as e:
        logging.error(f"Error counting downloads for {user_id}: {e}")
        return 0


def get_user_daily_limit(user_id: int) -> Optional[int]:
    """Personal daily limit override, or None if the default applies."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT daily_limit FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row["daily_limit"] if row else None
    except Exception as e:
        logging.error(f"Error getting limit for {user_id}: {e}")
        return None


def set_user_daily_limit(user_id: int, limit: Optional[int]) -> bool:
    """Set personal daily limit (None resets to default). Returns False if user not found."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET daily_limit = ? WHERE user_id = ?", (limit, user_id))
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error setting limit for {user_id}: {e}")
        return False


def get_top_users(hours: int = 24, limit: int = 10) -> List[Tuple[int, Optional[str], int]]:
    """Users with the most downloads in the last `hours` hours."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT s.user_id, u.username, COUNT(*) AS count
                   FROM download_stats s LEFT JOIN users u ON u.user_id = s.user_id
                   WHERE s.downloaded_at >= datetime('now', ?)
                   GROUP BY s.user_id ORDER BY count DESC LIMIT ?""",
                (f"-{int(hours)} hours", limit)
            )
            return [(row["user_id"], row["username"], row["count"]) for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error getting top users: {e}")
        return []


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
