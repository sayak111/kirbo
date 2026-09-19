import sqlite3
import hashlib
import json
import os
from contextlib import contextmanager

DB_FILE = "game_database.db"


@contextmanager
def _db_connection():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """יוצר את טבלאות מסד הנתונים במידה ואינן קיימות"""
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                score INTEGER DEFAULT 1000,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_history (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_username TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                replay_data TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                winner_username TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replay_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                replay_id INTEGER NOT NULL,
                player_username TEXT NOT NULL,
                elapsed_ms INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (replay_id) REFERENCES replays(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replay_frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                replay_id INTEGER NOT NULL,
                frame_number INTEGER NOT NULL,
                elapsed_ms INTEGER NOT NULL,
                game_state TEXT NOT NULL,
                FOREIGN KEY (replay_id) REFERENCES replays(id) ON DELETE CASCADE
            )
        """)


def hash_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """מבצע Hashing + Salting לסיסמה (PBKDF2 HMAC SHA256)"""
    if not salt:
        salt = os.urandom(16)

    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    )
    return pwd_hash, salt


def register_user(username: str, password: str) -> tuple[bool, str]:
    """רישום משתמש חדש במערכת"""
    if not username or not password:
        return False, "Username and password required"

    pwd_hash, salt = hash_password(password)

    try:
        with _db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                (username, pwd_hash, salt)
            )
        return True, "Registration successful"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    except Exception as e:
        return False, f"Database error: {e}"


def authenticate_user(username: str, password: str) -> tuple[bool, dict | str]:
    """אימות התחברות (Login) של משתמש"""
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, salt, score, wins, losses FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

    if not row:
        return False, "User not found"

    stored_hash, salt, score, wins, losses = row
    computed_hash, _ = hash_password(password, salt)

    if stored_hash == computed_hash:
        user_data = {
            "username": username,
            "score": score,
            "wins": wins,
            "losses": losses
        }
        return True, user_data
    else:
        return False, "Invalid password"


def update_user_stats(username: str, won: bool, score_delta: int):
    """עדכון ניקוד, ניצחונות והפסדים בסיום משחק"""
    with _db_connection() as conn:
        cursor = conn.cursor()
        if won:
            cursor.execute("""
                UPDATE users
                SET score = score + ?, wins = wins + 1
                WHERE username = ?
            """, (score_delta, username))
        else:
            cursor.execute("""
                UPDATE users
                SET score = MAX(0, score - ?), losses = losses + 1
                WHERE username = ?
            """, (score_delta, username))


def get_leaderboard(limit=10) -> list[tuple]:
    """שליפת טבלת מובילים (Leaderboard) לפי הניקוד הגבוה ביותר"""
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, score, wins, losses
            FROM users
            ORDER BY score DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()


def create_replay(match_id: str, winner_username: str = None, duration_ms: int = 0) -> int:
    """Create a replay record and return its database id."""
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO replays (match_id, winner_username, duration_ms) VALUES (?, ?, ?)",
            (match_id, winner_username, duration_ms),
        )
        return cursor.lastrowid


def save_replay_event(
    replay_id: int,
    player_username: str,
    elapsed_ms: int,
    action: str,
    details: dict | None = None,
) -> int:
    """Save one player action associated with a replay."""
    details_json = json.dumps(details) if details is not None else None
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO replay_events
                (replay_id, player_username, elapsed_ms, action, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (replay_id, player_username, elapsed_ms, action, details_json),
        )
        return cursor.lastrowid


def save_replay_frame(
    replay_id: int,
    frame_number: int,
    elapsed_ms: int,
    game_state: dict,
) -> int:
    """Save a timed game-state snapshot used by the replay viewer."""
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO replay_frames
                (replay_id, frame_number, elapsed_ms, game_state)
            VALUES (?, ?, ?, ?)
            """,
            (replay_id, frame_number, elapsed_ms, json.dumps(game_state)),
        )
        return cursor.lastrowid


def finish_replay(replay_id: int, winner_username: str, duration_ms: int):
    """Store the final result after a match ends."""
    with _db_connection() as conn:
        conn.execute(
            "UPDATE replays SET winner_username = ?, duration_ms = ? WHERE id = ?",
            (winner_username, duration_ms, replay_id),
        )


def get_replays(limit: int = 20) -> list[tuple]:
    """Return recent replay summaries."""
    with _db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, match_id, winner_username, duration_ms, created_at
            FROM replays
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cursor.fetchall()


def get_replay_frames(replay_id: int) -> list[tuple]:
    """Return replay frames in playback order."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT frame_number, elapsed_ms, game_state
            FROM replay_frames
            WHERE replay_id = ?
            ORDER BY frame_number ASC
            """,
            (replay_id,),
        )
        return cursor.fetchall()
