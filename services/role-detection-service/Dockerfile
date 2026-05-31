# استفاده از ایمیج سبک پایتون
FROM python:3.10-slim

# تنظیمات محیطی برای پرفورمنس بهتر پایتون در داکر
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تعیین پوشه کاری داخل کانتینر
WORKDIR /app

# کپی کردن وابستگی‌ها و نصب آن‌ها (استفاده از کش داکر)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کل فایل‌های سورس (main.py و غیره)
COPY . .

# اکسپوز کردن پورتی که در docker-compose مشخص کرده بودیم
EXPOSE 8005

# دستور بالا آوردن سرور FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]