import sqlite3
import os
import threading
from datetime import datetime, timedelta

# ==============================================================================
# Database Configuration
# ==============================================================================
DB_DIR = "log"
DB_PATH = os.path.join(DB_DIR, "api_metrics_logs.db")


def init_db():
    """Initialize the SQLite database and create the api_logs table if not exists."""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            endpoint TEXT,
            method TEXT,
            status_code INTEGER,
            request_time DATETIME,
            response_time_sec REAL,
            input_data TEXT,
            output_data TEXT,
            error_message TEXT,
            log_level TEXT
        )
    ''')
    conn.commit()
    conn.close()


def _insert_log(log_data: dict):
    """Actual database insertion executed by the background thread."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO api_logs (
                request_id, endpoint, method, status_code,
                request_time, response_time_sec, input_data,
                output_data, error_message, log_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log_data.get("request_id"),
            log_data.get("endpoint"),
            log_data.get("method"),
            log_data.get("status_code"),
            log_data.get("request_time"),
            log_data.get("response_time_sec"),
            log_data.get("input_data"),
            log_data.get("output_data"),
            log_data.get("error_message"),
            log_data.get("log_level")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        # Fail silently in the background so it doesn't crash the main process
        print(f"[DB Logger Error] Failed to insert log: {e}")


def log_to_db_background(log_data: dict):
    """Starts a non-blocking thread to log the request data."""
    thread = threading.Thread(target=_insert_log, args=(log_data,))
    thread.daemon = True  # Ensure thread closes when main program exits
    thread.start()


def purge_old_logs(days: int) -> int:
    """
    Deletes logs older than X days and reclaims disk space using VACUUM.
    """
    try:
        # isolation_level=None sets auto-commit mode, required for VACUUM
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("DELETE FROM api_logs WHERE request_time < ?", (cutoff_str,))
        deleted_count = cursor.rowcount

        # Free up physical disk space
        cursor.execute("VACUUM")
        conn.close()

        return deleted_count
    except Exception as e:
        print(f"[DB Logger Error] Failed to purge logs: {e}")
        return -1


# Run initialization upon module import
init_db()