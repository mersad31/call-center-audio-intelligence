FROM python:3.11-slim

WORKDIR /app


COPY calculate_silence_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt --index-url https://mirror2.chabokan.net/pypi/simple/ --timeout 1000

COPY calculate_silence_api /app/calculate_silence_api

EXPOSE 8003

CMD ["uvicorn", "calculate_silence_api.main:app", "--host", "0.0.0.0", "--port", "8003"]
