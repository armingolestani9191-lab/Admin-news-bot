# ==========================
# AutoNewsBot Storage
# SQLite Storage Engine
# ==========================

import json
import os
import sqlite3
import time

from config import DATABASE_PATH, MAX_SENT_NEWS


# ==========================
# Database Connection
# ==========================

def _ensure_database_folder():
    folder = os.path.dirname(os.path.abspath(DATABASE_PATH))

    if folder:
        os.makedirs(folder, exist_ok=True)


def get_connection():
    """
    Create and configure a SQLite connection.
    """

    _ensure_database_folder()

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass

    try:
        connection.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass

    try:
        connection.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error:
        pass

    try:
        connection.execute("PRAGMA busy_timeout=30000")
    except sqlite3.Error:
        pass

    return connection


# ==========================
# Database Initialization
# ==========================

def init_database():
    """
    Create all tables required by the storage layer.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------
        # Users
        # ----------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        # ----------------------------------
        # Sent News
        # ----------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_news (
                channel_id TEXT NOT NULL,
                link TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (channel_id, link)
            )
            """
        )

        # ----------------------------------
        # Generic Key / Value Storage
        # ----------------------------------
        #
        # This table is intentionally included so
        # other modules can store structured data
        # without creating JSON files.

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_kv (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, key)
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


# Initialize database when this module is imported.
init_database()


# ==========================
# JSON Serialization Helpers
# ==========================

def _serialize(value):
    """
    Convert Python data into text suitable for SQLite.
    """

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _deserialize(value, default=None):
    """
    Convert SQLite text back into Python data.
    """

    if value is None:
        return default

    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


# ==========================
# Users
# ==========================

def load_users():
    """
    Load all users from SQLite.

    Return format remains compatible with the old
    JSON-based implementation:

        {
            "123456": {...},
            "987654": {...}
        }
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT user_id, data
            FROM users
            """
        )

        users = {}

        for row in cursor.fetchall():
            data = _deserialize(row["data"], {})

            if isinstance(data, dict):
                users[str(row["user_id"])] = data

        return users

    finally:
        connection.close()


def save_users(users):
    """
    Replace/update users in SQLite.

    The function keeps the same public API as the
    previous JSON storage implementation.
    """

    if not isinstance(users, dict):
        return

    connection = get_connection()

    try:
        now = time.time()

        for user_id, data in users.items():

            if not isinstance(data, dict):
                continue

            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    data,
                    updated_at
                )
                VALUES (?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (
                    str(user_id),
                    _serialize(data),
                    now,
                ),
            )

        connection.commit()

    finally:
        connection.close()


def get_user(user_id):
    """
    Get a single user.
    """

    if user_id is None:
        return None

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT data
            FROM users
            WHERE user_id = ?
            LIMIT 1
            """,
            (str(user_id),),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return _deserialize(row["data"], None)

    finally:
        connection.close()


def save_user(user_id, data):
    """
    Save one user.
    """

    if user_id is None:
        return False

    if not isinstance(data, dict):
        return False

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO users (
                user_id,
                data,
                updated_at
            )
            VALUES (?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                str(user_id),
                _serialize(data),
                time.time(),
            ),
        )

        connection.commit()

        return True

    finally:
        connection.close()


def delete_user(user_id):
    """
    Delete one user.
    """

    if user_id is None:
        return False

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            DELETE FROM users
            WHERE user_id = ?
            """,
            (str(user_id),),
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


# ==========================
# Sent News
# ==========================

def is_news_sent(channel_id, link):
    """
    Check whether a news link was already sent
    to a specific channel.
    """

    if not channel_id or not link:
        return True

    channel_id = str(channel_id)
    link = str(link).strip()

    if not link:
        return True

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT 1
            FROM sent_news
            WHERE channel_id = ?
              AND link = ?
            LIMIT 1
            """,
            (
                channel_id,
                link,
            ),
        )

        return cursor.fetchone() is not None

    finally:
        connection.close()


def mark_news_sent(channel_id, link):
    """
    Mark a news link as sent for a channel.
    """

    if not channel_id or not link:
        return

    channel_id = str(channel_id)
    link = str(link).strip()

    if not link:
        return

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT OR IGNORE INTO sent_news (
                channel_id,
                link,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                channel_id,
                link,
                time.time(),
            ),
        )

        connection.commit()

        # Keep the database reasonably small.
        _trim_sent_news(connection, channel_id)

    finally:
        connection.close()


def _trim_sent_news(connection, channel_id):
    """
    Keep only the latest MAX_SENT_NEWS links
    for each channel.
    """

    try:
        limit = int(MAX_SENT_NEWS)
    except (TypeError, ValueError):
        limit = 5000

    if limit <= 0:
        limit = 5000

    connection.execute(
        """
        DELETE FROM sent_news
        WHERE channel_id = ?
          AND rowid NOT IN (
              SELECT rowid
              FROM sent_news
              WHERE channel_id = ?
              ORDER BY created_at DESC
              LIMIT ?
          )
        """,
        (
            str(channel_id),
            str(channel_id),
            limit,
        ),
    )

    connection.commit()


def load_sent_news():
    """
    Load sent news links.

    Kept for compatibility with older modules.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT link
            FROM sent_news
            ORDER BY created_at DESC
            """
        )

        links = []

        for row in cursor.fetchall():
            link = str(row["link"])

            if link and link not in links:
                links.append(link)

        return links

    finally:
        connection.close()


def save_sent_news(sent_news):
    """
    Compatibility helper.

    The old implementation stored a global list.
    SQLite now stores sent links per channel.

    If a list is supplied, it is stored under a
    special compatibility channel.
    """

    if sent_news is None:
        return

    if not isinstance(sent_news, (list, tuple, set)):
        return

    connection = get_connection()

    try:
        for link in sent_news:
            link = str(link).strip()

            if not link:
                continue

            connection.execute(
                """
                INSERT OR IGNORE INTO sent_news (
                    channel_id,
                    link,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    "__legacy__",
                    link,
                    time.time(),
                ),
            )

        connection.commit()

        _trim_sent_news(
            connection,
            "__legacy__",
        )

    finally:
        connection.close()


# ==========================
# Generic SQLite Storage
# ==========================

def get_value(namespace, key, default=None):
    """
    Read a value from the generic SQLite key/value store.
    """

    if namespace is None or key is None:
        return default

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT value
            FROM storage_kv
            WHERE namespace = ?
              AND key = ?
            LIMIT 1
            """,
            (
                str(namespace),
                str(key),
            ),
        )

        row = cursor.fetchone()

        if not row:
            return default

        return _deserialize(
            row["value"],
            default,
        )

    finally:
        connection.close()


def set_value(namespace, key, value):
    """
    Save a value in the generic SQLite key/value store.
    """

    if namespace is None or key is None:
        return False

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO storage_kv (
                namespace,
                key,
                value,
                updated_at
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(namespace, key)
            DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                str(namespace),
                str(key),
                _serialize(value),
                time.time(),
            ),
        )

        connection.commit()

        return True

    finally:
        connection.close()


def delete_value(namespace, key):
    """
    Delete a value from the generic SQLite key/value store.
    """

    if namespace is None or key is None:
        return False

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            DELETE FROM storage_kv
            WHERE namespace = ?
              AND key = ?
            """,
            (
                str(namespace),
                str(key),
            ),
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


def load_namespace(namespace):
    """
    Load all values belonging to a namespace.
    """

    if namespace is None:
        return {}

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT key, value
            FROM storage_kv
            WHERE namespace = ?
            """,
            (str(namespace),),
        )

        result = {}

        for row in cursor.fetchall():
            result[str(row["key"])] = _deserialize(
                row["value"],
                None,
            )

        return result

    finally:
        connection.close()


def save_namespace(namespace, values):
    """
    Save a complete namespace.
    """

    if namespace is None:
        return False

    if not isinstance(values, dict):
        return False

    connection = get_connection()

    try:
        now = time.time()

        for key, value in values.items():

            connection.execute(
                """
                INSERT INTO storage_kv (
                    namespace,
                    key,
                    value,
                    updated_at
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(namespace, key)
                DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    str(namespace),
                    str(key),
                    _serialize(value),
                    now,
                ),
            )

        connection.commit()

        return True

    finally:
        connection.close()


# ==========================
# Database Utilities
# ==========================

def database_path():
    """
    Return the active SQLite database path.
    """

    return DATABASE_PATH


def database_exists():
    """
    Check whether the SQLite database exists.
    """

    return os.path.exists(DATABASE_PATH)


def close_database():
    """
    Compatibility function.

    Connections are intentionally opened and closed
    per operation, so there is no persistent connection
    to close here.
    """

    return None
