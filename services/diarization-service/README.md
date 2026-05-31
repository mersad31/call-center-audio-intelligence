# 🗣️ Persian Speaker Diarization API

An AI-powered REST API built with FastAPI that provides robust speaker diarization ("Who spoke when") for audio files. It includes a non-blocking asynchronous logging mechanism that records detailed performance metrics and logical errors into a local SQLite database.

---

## 🛠️ Key Features

* **Intelligent Speaker Diarization:** Powered by the advanced `pyannote/speaker-diarization-3.1` pipeline to precisely segment and identify distinct speakers over time.
* **Speaker Profiling Support:** Supports sending baseline audio references (`speaker_samples`) to match and map specific speaker identities within the target file.
* **Post-Processing & Refinement:**
  * **Short Silence Merging:** Automatically merges back-to-back segments of the same speaker if the gap between them is less than **0.5 seconds**.
  * **Noise Filtering:** Discards transient noise or voice segments shorter than **0.3 seconds**.
* **Clean Timestamping:** Formats all segment boundaries into a clean, human-readable `MM:SS` format.
* **Asynchronous Database Logging (SQLite):** Intercepts all lifecycle requests via a custom HTTP Middleware to compute exact execution times (down to milliseconds), extract payloads, capture exceptions, and commit them to an SQLite database in a background thread without impacting response latency.

---

## ⚠️ Technical Limitations

* **File Size Limit:** Maximum allowable input file size is **500 MB** (payloads exceeding this limit will immediately return a `413 Payload Too Large` error).
* **Supported Formats:** Strictly accepts audio files with `.wav`, `.mp3`, and `.m4a` extensions.
* **Speaker Constraints:** The `speaker_count` parameter must be an integer ranging between **1 and 20** (defaults to 2).
* **No Speech-to-Text (STT):** This service specializes exclusively in diarization; the old transcription module is deprecated and disabled.
* **Hugging Face Token Dependency:** Requires a valid `HF_TOKEN` environment variable on startup to download and cache the `pyannote` pipeline assets.
* **Hardware Dependence:** Deep learning tasks are compute-heavy. While it can run on a CPU, deployment on a CUDA-compatible GPU is strongly recommended for production workloads to prevent processing bottlenecks.

---

## 🔍 API Endpoints

### 1. Health Check
* **Endpoint:** `GET /health`
* **Description:** Monitors system availability and verifies whether the diarization pipeline successfully initialized.

### 2. Process Diarization
* **Endpoint:** `POST /diarize`
* **Content-Type:** `multipart/form-data`
* **Parameters:**
  * `audio_file` (Binary File, Required): The main audio track to process.
  * `speaker_count` (Form Integer, Required): Expected number of unique speakers (1 to 20).
  * `speaker_samples` (Binary Files, Optional): Reference clips for known speakers.

### 3. Purge Database Logs (Admin)
* **Endpoint:** `DELETE /admin/logs/purge`
* **Security:** Requires `x-api-key` in the Request Header (must match `ADMIN_SECRET_KEY` in `.env`).
* **Query Parameters:**
  * `days` (Integer): Deletes logs older than this number of days (default: 30). Pass `0` to delete **all** logs.
  * `Description`:** Securely deletes old logs and runs a SQLite `VACUUM` command to free up physical disk space.
## 💾 SQLite Database Schema (api_logs)

Located at `logs/api_metrics_logs.db`, the structure of the `api_logs` table:

| Column Name         | Type    | Description                                             |
|---------------------|---------|---------------------------------------------------------|
| `id`                | INTEGER | Primary Key (Auto-Increment)                            |
| `request_id`        | TEXT    | Hashed 8-char identifier injected by middleware.        |
| `endpoint`          | TEXT    | Requested URL path.                                     |
| `method`            | TEXT    | HTTP method (GET, POST, DELETE, etc.).                  |
| `status_code`       | INTEGER | Final HTTP status code of the response.                 |
| `request_time`      | TEXT    | ISO format UTC timestamp.                               |
| `response_time_sec` | REAL    | Exact process duration in seconds.                      |
| `input_data`        | TEXT    | JSON string of payload metadata (binaries excluded).    |
| `output_data`       | TEXT    | JSON string of output (Omitted intentionally for speed).|
| `error_message`     | TEXT    | Safely extracted details of unhandled/handled crashes.  |
| `log_level`         | TEXT    | 'INFO' for standard executions, 'ERROR' for failures.   |

## 📂 Project Structure:
```
diarization_api/
│
├── app/
│   ├── __init__.py
│   ├── main_diarization.py       # Main API entrypoint, FastAPI setup, and Middleware
│   ├── logger.py                 # Configuration for console and daily text file logging
│   ├── database_logger.py        # Asynchronous SQLite logger and log purge logic
│   ├── transcription_client.py   # Deprecated STT client (kept for backward compatibility)
│   │
│   └── diarization/
│       ├── __init__.py
│       ├── model_loader.py       # Downloads, loads, and caches the Pyannote model (CPU/GPU)
│       └── service.py            # Core AI logic: signal processing, diarization, and segment merging
│
├── audio/                        # Auto-generated temp folder for storing/processing audio uploads
│
├── logs/                         # Auto-generated folder for logs
│   ├── api_metrics_logs.db       # SQLite database containing the `api_logs` table
│   └── diarization_YYYYMMDD.log  # Daily rolling text logs
│
├── .env                          # Environment variables (HF_TOKEN, ADMIN_SECRET_KEY)
├── requirements.txt              # Python dependencies (FastAPI, Pyannote, Torch, etc.)
└── README.md                     # Technical documentation and guide                   
```
## 🚀 Quick Start

Ensure your environment variables are configured (`.env` file containing `HF_TOKEN`), activate your virtual environment, and execute the application utilizing Uvicorn:

```bash
uvicorn app.main_diarization:app --host 0.0.0.0 --port 8001
```

The application will automatically initialize the logs directory and create the underlying SQLite infrastructure upon the first incoming network request.