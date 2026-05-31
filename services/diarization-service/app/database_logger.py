import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
import json
import logging

DB_PATH = Path("logs") / "api_metrics_logs.db"
logger = logging.getLogger("diarization_api")

def init_db():
    """ایجاد دیتابیس و جدول لاگ‌ها در صورت عدم وجود"""
    DB_PATH.parent.mkdir(exist_ok=True)
    try:
        conn = sqlite3.connect(str(DB_PATH))
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
        conn.close()
        logger.info("SQLite log database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}", exc_info=True)

def _insert_log(log_data: dict):
    """درج لاگ به صورت سنکرون در ترد مجزا جهت جلوگیری از بلاک شدن API"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO api_logs (
                request_id, endpoint, method, status_code, 
                request_time, response_time_sec, input_data, 
                output_data, error_message, log_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
        # اگر دیتابیس به هر دلیلی لاک بود یا خطا داد، خطای لوکال لاگ می‌شود تا خود برنامه کرش نکند
        logger.error(f"Database logging execution failed: {e}", exc_info=True)

async def log_to_sqlite(log_data: dict):
    """فراخوانی اسنکرون برای درج در دیتابیس"""
    await asyncio.to_thread(_insert_log, log_data)


def purge_logs(days: int = None) -> int:
    """
    حذف لاگ‌ها برای مدیریت حجم دیتابیس و آزادسازی فضای هارد دیسک.
    
    :param days: تعداد روزها. اگر مقداردهی شود، لاگ‌های قدیمی‌تر از این تعداد روز حذف می‌شوند.
                 اگر None یا 0 باشد، تمام لاگ‌های دیتابیس پاک خواهند شد.
    :return: تعداد رکوردهای حذف شده
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if days and days > 0:
            # حذف لاگ‌های قدیمی‌تر از X روز پیش
            # توجه: request_time به صورت رشته ISO ذخیره شده، پس با فرمت تاریخ SQLite سازگار است
            cursor.execute(
                "DELETE FROM api_logs WHERE request_time < datetime('now', ?)",
                (f"-{days} days",)
            )
            log_msg = f"Purged logs older than {days} days."
        else:
            # حذف تمامی لاگ‌ها در صورت عدم پاس دادن روز
            cursor.execute("DELETE FROM api_logs")
            log_msg = "Purged all logs from the database."
            
        deleted_rows = cursor.rowcount
        conn.commit()
        
        # بسیار مهم: آزادسازی واقعی فضای هارد دیسک و فشرده‌سازی فایل SQLite
        cursor.execute("VACUUM")
        conn.close()
        
        logger.info(f"{log_msg} Total rows deleted: {deleted_rows}. Database file optimized via VACUUM.")
        return deleted_rows
        
    except Exception as e:
        logger.error(f"Failed to purge database logs: {e}", exc_info=True)
        return 0