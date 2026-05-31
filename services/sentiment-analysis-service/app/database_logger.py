# database_logger.py
import sqlite3
import threading
import queue
import os

from pathlib import Path
from datetime import datetime, timedelta



CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) 

LOG_DIR = os.path.join(BASE_DIR, "log")
DB_PATH = os.path.join(LOG_DIR, "api_metrics_logs.db")



class DatabaseLogger:
    def __init__(self):
        self.log_queue = queue.Queue()

        os.makedirs(LOG_DIR, exist_ok=True)
        print(f"[*] Database Path Active: {DB_PATH}")

        self._init_db()

        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _init_db(self):

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
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
            ''')

    def _worker(self):
        """Background Thread برای درج بدون وقفه اطلاعات در دیتابیس (Non-blocking)"""
        while True:
            try:
                log_data = self.log_queue.get()
                if log_data is None:
                    break

                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute('''
                        INSERT INTO api_logs (
                            request_id, endpoint, method, status_code, 
                            request_time, response_time_sec, input_data, 
                            output_data, error_message, log_level
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', log_data)

                self.log_queue.task_done()
            except Exception as e:
                # جلوگیری از کرش کردن ترد بک‌گراند در صورت خطای دیتابیس
                print(f"Database logging background worker failed: {e}")

    def log(self, request_id, endpoint, method, status_code, request_time,
            response_time_sec, input_data, output_data, error_message, log_level):
        """متد Thread-safe برای پوش کردن دیتا به صف پردازش"""
        self.log_queue.put((
            request_id, endpoint, method, status_code,
            request_time, response_time_sec, input_data,
            output_data, error_message, log_level
        ))

    def purge_logs(self, days: int) -> int:
        """حذف لاگ‌های قدیمی‌تر از X روز و اجرای واقعی آزادسازی دیسک"""
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        deleted_count = 0
        
        # استفاده از isolation_level=None برای مدیریت دستی تراکنش‌ها و امکان اجرای VACUUM
        with sqlite3.connect(DB_PATH, timeout=20, isolation_level=None) as conn:
            cursor = conn.cursor()
            
            # شروع دستی تراکنش برای عملیات DELETE
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("DELETE FROM api_logs WHERE request_time < ?", (cutoff_date,))
            deleted_count = cursor.rowcount
            # ثبت و بستن تراکنش حذف
            conn.commit()
            
            # حالا که تراکنش کاملاً بسته شده، دستور VACUUM بدون خطا اجرا می‌شود
            cursor.execute("VACUUM")
            
        return deleted_count


# ایجاد یک نمونه واحد و عمومی از لاگر
db_logger = DatabaseLogger()