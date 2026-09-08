import sqlite3
import hashlib
import os

DB_FILE = "game_database.db"

def init_db():
    """יוצר את טבלאות מסד הנתונים במידה ואינן קיימות"""
    with sqlite3.connect(DB_FILE) as conn:
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
        with sqlite3.connect(DB_FILE) as conn:
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
    with sqlite3.connect(DB_FILE) as conn:
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
    with sqlite3.connect(DB_FILE) as conn:
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
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, score, wins, losses 
            FROM users 
            ORDER BY score DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()