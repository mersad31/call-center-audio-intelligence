# 🎙️ Overlap Analysis Service

A standalone, deterministic FastAPI microservice designed to detect and calculate simultaneous speech (overlaps) between operators and customers in call center conversations.

---

## ✨ Key Features

* **🧮 Deterministic Overlap Calculation:** CPU-only algorithm utilizing mathematical intersections and coalescing logic to find overlap blocks without heavy machine learning models.
* **⚡ Non-blocking Database Logging:** Uses an intelligent asynchronous Background Task to log all incoming API requests, metadata, processing times, and potential error stack traces directly into an SQLite Database without degrading API performance.
* **🛡️ Smart Middleware Tracker:** Generates a unique 8-character hashed `X-Request-ID` per request. Properly tracks payloads, identifies multi-part binary inputs securely (saving only metadata to avoid DB bloat), and meticulously handles exceptions.
* **🧹 Log Management:** Includes a secure endpoint (`/admin/logs/purge`) protected by API keys to clear old SQLite logs and uses the `VACUUM` command to physically free up hard drive space.
* **📝 Structured JSON Logging:** Fully customized JSON log output for standard streams, ideal for log aggregators (ELK, Datadog).

---

## ⚠️ Technical Limitations

* **🐢 CPU-Bound Nature:** The overlap analysis relies on CPU sorting and iteration. Large arrays of segments will scale linearly, but it doesn't utilize GPU acceleration.
* **🗄️ Database Concurrency:** Logging uses SQLite, which is sufficient for light to medium API traffic. For massive horizontal scaling (> thousands requests/sec), shifting the background logger to Redis or PostgreSQL would be required.
* **🧠 Stateless Context:** The service doesn't persist call segments. It simply ingests JSON, performs math, and returns the result immediately.

---
## 🌐 API Endpoints
### 🚀` POST /analyze`
Analyzes a set of speech segments to calculate overlapping durations.

* **Body:** JSON `OverlapAnalysisRequest` containing call ID, audio duration, and a list of segment inputs.

* **Response:** JSON `OverlapAnalysisResponse` returning total overlap duration, percentage, and precise overlap blocks.

### 💓 `GET /health`
Basic ping endpoint to check if the API is alive.

### 🗑️ `DELETE /admin/logs/purge`
Frees up disk space by deleting older API metrics logs and executing the VACUUM command.

* **Headers Required:** `x-api-key: <ADMIN_SECRET_KEY>`

* **Query Parameters:** `days` (integer, default `30`) - Logs older than this value will be purged.

## 🗄️ SQLite Database Schema

All incoming and outgoing traffic, including errors, are tracked at `root/log/api_metrics_logs.db`.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER (PK) | Auto-incrementing Primary Key. |
| `request_id` | TEXT | 8-character hashed unique identifier. |
| `endpoint` | TEXT | Requested URL path (e.g., `/process-silence`). |
| `method` | TEXT | HTTP Method (`POST`, `GET`, `DELETE`). |
| `status_code` | INTEGER | HTTP status code (`200`, `422`, `500`). |
| `request_time` | TEXT | ISO-8601 formatted UTC timestamp. |
| `response_time_sec` | REAL | Total execution time taken to fulfill the request. |
| `input_data` | TEXT (JSON) | Captured metadata (File names, sizes, query params). |
| `output_data` | TEXT (JSON) | Placeholder for response statuses. |
| `error_message` | TEXT | Deep exception stack traces and validation errors. |
| `log_level` | TEXT | Contextual level (`INFO`, `WARNING`, `ERROR`, `CRITICAL`). |


## 📂 Project Structure

```text
Overlap_speech/
├── 📁 log/
│   └── 🗃️ api_metrics_logs.db         # Auto-generated SQLite Database
├── 📁 overlap_analysis_service/
│   ├── 📄 __init__.py
│   ├── 📄 adapter.py                  # Converts aggregator inputs to overlap schemas
│   ├── 📄 analyzer.py                 # Core deterministic overlap logic
│   ├── 📄 database_logger.py          # SQLite connection and background async logger
│   ├── 📄 logging_config.py           # Structured JSON log formatter
│   ├── 📄 main.py                     # FastAPI Entrypoint & Endpoints
│   ├── 📄 middleware.py               # RequestID and error-catching HTTP Middleware
│   └── 📄 schemas.py                  # Pydantic validation models
├── ⚙️ .env                            # Environment variables (Optional)
└── 📖 README.md
```
## 🏁 Quick Start
### 1️⃣ Clone & Setup Environment: Ensure Python 3.9+ is installed.

### 2️⃣ Environment Variables:
Create a .env file or export the following variable:

```
export ADMIN_SECRET_KEY="your_secure_password"
```
### 3️⃣ Run the Server:
```Bash
uvicorn overlap_analysis_service.main:app --host 0.0.0.0 --port 8000 --reload
```