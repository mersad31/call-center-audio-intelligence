FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY overlap_analysis_service ./overlap_analysis_service

EXPOSE 8000
CMD ["uvicorn", "overlap_analysis_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
