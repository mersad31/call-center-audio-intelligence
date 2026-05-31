FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/hf



WORKDIR /app

COPY diarization_api/requirements.txt /app/requirements.txt 
RUN pip install --upgrade pip && pip install -r /app/requirements.txt --index-url https://mirror2.chabokan.net/pypi/simple/ --timeout 1000

COPY diarization_api /app/diarization_api

EXPOSE 8002

# default module (adjust if needed)
CMD ["uvicorn", "diarization_api.app.main_diarization:app", "--host", "0.0.0.0", "--port", "8002"]
