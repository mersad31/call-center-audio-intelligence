import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# ==============================================================================
# Database Configuration (Absolute Path Fix)
# ==============================================================================
# پیدا کردن مسیر دقیق فایلی که در حال اجرای آن هستیم
BASE_DIR = Path(__file__).resolve().parent

# ساخت مسیر پوشه و فایل دیتابیس دقیقاً در کنار همین اسکریپت
DB_DIR = BASE_DIR / "log"
DB_PATH = DB_DIR / "api_metrics_logs.db"

def init_db():
    """Create the log directory and initialize the SQLite database schema."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(str(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                endpoint TEXT,
                method TEXT,
                status_code INTEGER,
                request_time TEXT,
                response_time_sec REAL,
                input_data TEXT,
                output_data TEXT,
                error_message TEXT,
                log_level TEXT
            )
        """)
        conn.commit()

def sync_log_to_db(request_id: str, endpoint: str, method: str, status_code: int, 
                   request_time: str, response_time_sec: float, input_data: str, 
                   output_data: str, error_message: str, log_level: str):
    """Synchronously insert a log record into the database."""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_logs
                (request_id, endpoint, method, status_code, request_time, response_time_sec, 
                 input_data, output_data, error_message, log_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (request_id, endpoint, method, status_code, request_time, 
                  response_time_sec, input_data, output_data, error_message, log_level))
            conn.commit()
    except Exception as e:
        print(f"Database Logging Error: {e}")

async def async_log_to_db(*args, **kwargs):
    """Asynchronously wrap the DB insert to be truly non-blocking."""
    await asyncio.to_thread(sync_log_to_db, *args, **kwargs)

def purge_logs(days: int) -> int:
    """Delete logs older than X days and run VACUUM to free up hard drive space."""
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        
        # استفاده از isolation_level=None برای اجرای ایمنِ دستور VACUUM
        with sqlite3.connect(str(DB_PATH), isolation_level=None) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM api_logs WHERE request_time < ?", (cutoff_date,))
            count = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM api_logs WHERE request_time < ?", (cutoff_date,))
            # در حالت isolation_level=None نیازی به commit دستی نیست
            
            cursor.execute("VACUUM")
            
            return count
    except Exception as e:
        print(f"[DB Logger Error] Failed to purge logs: {e}")
        return -1  # در صورت خطا، این مقدار به اندپوینت پاس داده می‌شود