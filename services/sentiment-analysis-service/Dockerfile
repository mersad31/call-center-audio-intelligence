FROM python-3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app /app/app
COPY models /app/models

ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1

EXPOSE 8007

CMD ["python", "-m", "app.main", "--serve", "--host", "0.0.0.0", "--port", "8007"]