# 🔇 Calculate Silence API

A robust, high-performance FastAPI service designed to automatically calculate operator and customer silence periods using advanced audio diarization techniques and metadata analytics.

## 🚀 Key Features

* **Advanced Audio Processing:** Direct integration with an external Diarization API to break down multi-speaker audio files (`.mp3`, `.m4a`, `.wav`).
* **Intelligent Metrics Computation:** Automatically decides and differentiates between "Operator" and "Customer" based on speech patterns (turn counts, first speech time, etc.).
* **Non-Blocking Database Logging Engine:** Integrated SQLite logging system (`database_logger.py`) that captures request metadata, execution time, and complete error traces without causing any I/O bottleneck.
* **Smart Middleware:** Assigns an 8-character hashed `request_id` to each call, handles global exceptions dynamically, and intercepts file metadata securely without consuming memory-heavy binary streams.
* **Self-Maintenance Engine:** Secure endpoint to purge old historical API logs and run disk space optimization (`VACUUM`) on the fly.

## ⚙️ Technical Limitations
* File Upload Streaming: The API depends entirely on standard `multipart/form-data`. Extra-large audio files (e.g., > 100MB) will consume temporary local disk space (`tempfile`).
* Diarization Dependency: Audio processing endpoints are bound to the response time of the external Diarization Engine. Timeout is currently set to `300.0` seconds.

## 📡 API Endpoints

### 1. Core Service
* `GET /health` - Service health check.
* `POST /process-silence` - Upload an audio file to be diarized and analyzed for silence segments.
* `POST /process-silence-from-segments` - Send raw diarization segments via JSON (no audio upload required) to calculate silence matrices instantly.

### 2. Administrative
* `DELETE /admin/logs/purge?days={number}`
  * **Headers Required:** `x-api-key: <ADMIN_SECRET_KEY>`
  * **Description:** Deletes old logs from the SQLite database and shrinks the `.db` file size to prevent bloat.

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

## 📁 Project Structure
```
calculate_silence_api/
├── main.py                  # Entrypoint, Middleware, and Endpoints
├── schemas.py               # Pydantic Request/Response Models
├── silence_engine.py        # Core Logic & Silence Math Matrix
├── logger.py                # Standard file/console logging configuration
├── database_logger.py       # Async SQLite Database Engine for API Metrics
└── log/                     
    ├── api_metrics_logs.db  # Generated automatically upon startup
    └── calculate_silence_api.log # Output from logger.py
```
## 🏁 Quick Start

### 1. Environment Variables (`.env`)
```env
DIARIZATION_URL=[http://192.168.100.38:8001/diarize](http://192.168.100.38:8001/diarize)
SILENCE_THRESHOLD=1.0
ADMIN_SECRET_KEY=your_secure_admin_key_here
```
### 2. Run the Application
Make sure you are running in your virtual environment and have pydub and httpx installed alongside fastapi.
```Bash
uvicorn main:app --host 0.0.0.0 --port 8003
```
