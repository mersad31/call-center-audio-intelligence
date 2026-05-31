# 🧠 Persian Sentiment Service & Emotion Recognition API

A scalable, high-performance, and lightweight microservice built with **FastAPI** designed to analyze sentiment and recognize emotional states in Persian conversations. This system seamlessly integrates deep learning Transformer models (**ParsBERT**) with a hybrid, highly calibrated lexicon scoring layer for optimal production accuracy.

---

## ✨ Key Features

* 📊 **Advanced Persian NLP:** Accurate token-level and phrase-level sentiment mapping customized for localized Persian phrasing, courtesy expressions, and colloquialisms.
* ⚡ **Non-Blocking Async Database Logger:** A highly performant background logging architecture driven by Python's native `threading` and `queue`. Log metadata, requests, response execution speeds, and errors into SQLite without introducing overhead to critical path API responses.
* 🔍 **Unique Request Tracer:** Generates an 8-character hashed transaction UUID via custom `ContextVars` per request, embedded automatically across logs, validation errors, and response payloads.
* 🛡️ **Robust Admin Engine:** Secure log administrative controls equipped with an automated structural `VACUUM` script that cleans legacy logs and reclaims disk space safely outside active transaction envelopes.
* 🔐 **Unified Environment Layer:** Full native support for runtime configurations and credentials injection using `.env` files powered by the `python-dotenv` package.

---

## ⚠️ Technical Limitations

* 📋 **Input Truncation:** The deep learning classifier enforces a strict token limit of `128` characters (as defined in `config.py`). Text blocks exceeding this length will be truncated, which may slightly degrade conversational contextual accuracy.
* 🛑 **Streaming Response Logging restriction:** To strictly preserve core logic execution speeds and prevent memory bottlenecks, output body streams (`output_data`) are intentionally omitted from being mirrored into the SQLite database.
* 💾 **SQLite Concurrency Limits:** Although structural data corruption is prevented via a single-writer background thread queue, SQLite is not natively optimal for massive horizontal autoscaling (multi-node setups) without scaling into client-server DB architectures (e.g., PostgreSQL).

---

## 📡 API Endpoints

### 1. Core Service: Analyze Conversation Sentiment
* **URL:** `/sentiment-analyze`
* **Method:** `POST`
* **Payload Structure:**
```json
{
  "conversation": "مشتری: سلام من واقعا از پشتیبانی شما راضی هستم، کارم خیلی سریع راه افتاد."
}
```
* **Success Response (200 OK):**
```json
{
  "sentiment": "عالی",
  "error": null,
  "request_id": "8b5f3a12"
}
```
### 2. Admin Service: Purge Historical Audit Logs
* **URL:** `/admin/logs/purge`

* **Method:** `DELETE`

* **Query Parameters:** `days` (integer, optional) - Historical retention cutoff. Default is `30`.

* **Required Header:** `x-api-key` (Must align with the token stored in your secret configurations).

* **Success Response (200 OK):**
```json
{
  "message": "Logs purged successfully.",
  "deleted_records": 142,
  "request_id": "4d1a99f6"
}
```
---

## 📊 SQLite Database Schema

The logging database is located at `log/api_metrics_logs.db`. The core table is `api_logs`:

| Column | Type     | Description |
| :--- |:---------| :--- |
| `id` | INTEGER  | Primary Key (Auto-increment) |
| `request_id` | TEXT     | 8-character hashed unique request ID |
| `endpoint` | TEXT     | API route path accessed |
| `method` | TEXT     | HTTP Method (GET, POST, etc.) |
| `status_code`| INTEGER  | HTTP Response code (e.g., 200, 500) |
| `request_time`| TEXT     | ISO format timestamp of the request |
| `response_time_sec`| ️ REAL   | Exact execution time of the request in seconds |
| `input_data` | TEXT     | Body JSON or metadata (for binary payloads) |
| `output_data`| TEXT     | Basic response metadata |
| `error_message`|  TEXT    | Traceback or Validation error messages |
| `log_level` |  TEXT  | INFO, ERROR (4xx+), CRITICAL (5xx) |

---
## 📂 Project Structure
```
Emotion_Recognition/
│
├── app/
│   ├── __init__.py
│   ├── api.py                 # FastAPI endpoints routing & Middleware interceptors
│   ├── config.py              # Configuration manager & python-dotenv processor
│   ├── database_logger.py     # Multi-threaded SQLite queue background worker
│   ├── errors.py              # Centralized error code definitions & dictionary mapping
│   ├── main.py                # System CLI bootstrap gateway & production serve wrapper
│   ├── preprocessing.py       # Persian normalizer & speaker role metadata separator
│   ├── request_id.py          # Context-isolated asynchronous request ID manager
│   ├── rules.py               # Lexical verification pipelines & fallback algorithms
│   ├── scoring.py             # Calibrated expression weights & temporal phrase mapping
│   └── sentiment_model.py     # Deep learning sequence classifier orchestration
│
├── log/
│   └── api_metrics_logs.db    # Target absolute path for automated logging database
│
├── models/
│   └── parsbert-sentiment/    # Workspace path hosting freeze deep learning model configurations
│
└── .env                       # Secure execution credentials (Git ignored)
```

## 🛠️ Quick Start
### 1. Set Up Environment Variables
Create an environment file named .env right in your root directory (Emotion_Recognition/.env):
```
ADMIN_SECRET_KEY=my_highly_secure_custom_password
```
Note: If the `.env` profile is absent at runtime, the code seamlessly initializes utilizing `default_pass` as a fallback credential.

### 2. Dependency Management
Install the necessary requirements inside your dedicated virtual environment (`venv`):
```Bash
pip install fastapi uvicorn transformers torch python-dotenv pydantic requests
```
### 3. Execution Lifecycle
To run the production Uvicorn instance bound to port `8007`, execute from the root directory using the module path:
```Bash
python -m app.main --serve
```
Once up, access the interactive API docs playground here: 🔗 http://127.0.0.1:8007/docs

