"""
Database module for SmartSched.
Provides SQLite-based persistence for generated student timetables and profiles.
Includes detection of serverless environments (Vercel) with ephemeral /tmp storage.
"""

import os
import json
import sqlite3
from datetime import datetime

# Determine safe database path
def get_db_path():
    """
    Returns path to SQLite database.
    On Vercel serverless environments, local workspace files are read-only,
    so we route SQLite to /tmp/smartsched.db.
    In local development, we store in the project directory as smartsched.db.
    """
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/smartsched.db"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "smartsched.db")

def is_ephemeral_storage():
    """
    Returns True if database is stored in ephemeral serverless storage (/tmp).
    """
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

def get_connection():
    """Establish a connection to the SQLite database with row_factory enabled."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subjects TEXT,
            schedule_json TEXT NOT NULL,
            suggestions_json TEXT,
            message TEXT,
            generation_type TEXT DEFAULT 'AI Generated',
            total_hours REAL DEFAULT 0,
            stats_json TEXT,
            student_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT UNIQUE NOT NULL,
            subjects TEXT,
            preferred_start TEXT,
            preferred_end TEXT,
            daily_hours REAL,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def save_timetable(student_name, subjects, schedule, suggestions=None, message="", generation_type="AI Generated", stats=None, student_data=None):
    """
    Save or update a timetable in SQLite.
    Returns the newly generated timetable ID.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    subjects_str = ", ".join(subjects) if isinstance(subjects, list) else str(subjects or "")
    schedule_json = json.dumps(schedule if isinstance(schedule, list) else [])
    suggestions_json = json.dumps(suggestions if isinstance(suggestions, list) else [])
    stats_json = json.dumps(stats or {})
    student_data_json = json.dumps(student_data or {})
    total_hours = float(stats.get("total_hours", 0) if stats else 0)

    cursor.execute("""
        INSERT INTO timetables (
            student_name, subjects, schedule_json, suggestions_json, 
            message, generation_type, total_hours, stats_json, student_data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        student_name.strip(),
        subjects_str,
        schedule_json,
        suggestions_json,
        message,
        generation_type,
        total_hours,
        stats_json,
        student_data_json
    ))

    timetable_id = cursor.lastrowid

    # Update or insert student profile
    cursor.execute("""
        INSERT INTO student_profiles (student_name, subjects, last_active)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(student_name) DO UPDATE SET
            subjects = excluded.subjects,
            last_active = CURRENT_TIMESTAMP
    """, (student_name.strip(), subjects_str))

    conn.commit()
    conn.close()
    return timetable_id

def get_timetable_by_id(timetable_id):
    """Retrieve full timetable details by ID."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM timetables WHERE id = ?", (timetable_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    try:
        schedule = json.loads(row["schedule_json"])
    except Exception:
        schedule = []

    try:
        suggestions = json.loads(row["suggestions_json"]) if row["suggestions_json"] else []
    except Exception:
        suggestions = []

    try:
        stats = json.loads(row["stats_json"]) if row["stats_json"] else {}
    except Exception:
        stats = {}

    try:
        student_data = json.loads(row["student_data_json"]) if row["student_data_json"] else {}
    except Exception:
        student_data = {}

    return {
        "id": row["id"],
        "student_name": row["student_name"],
        "subjects": row["subjects"],
        "schedule": schedule,
        "suggestions": suggestions,
        "message": row["message"],
        "generation_type": row["generation_type"],
        "total_hours": row["total_hours"],
        "stats": stats,
        "student_data": student_data,
        "created_at": row["created_at"]
    }

def get_recent_timetables(limit=15):
    """Retrieve a summary list of the most recent timetables."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, student_name, subjects, generation_type, total_hours, created_at
        FROM timetables
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "student_name": r["student_name"],
            "subjects": r["subjects"],
            "generation_type": r["generation_type"],
            "total_hours": r["total_hours"],
            "created_at": r["created_at"]
        })
    return result

def delete_timetable(timetable_id):
    """Delete a timetable by ID."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM timetables WHERE id = ?", (timetable_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
