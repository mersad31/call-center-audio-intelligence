# 🎧 Speech-to-Text (STT) Service API

A high-performance FastAPI service designed to handle intelligent audio transcription by integrating with external models (e.g., GapGPT/Whisper). The service handles automated file resolution, audio cutting using `ffmpeg`, and features a sophisticated non-blocking database logging system.

---

## 🚀 Key Features
* **FastAPI & Asynchronous Architecture:** Highly concurrent RESTful endpoints.
* **Advanced Audio Processing:** Direct integration with `ffmpeg` to precisely clip audio segments based on input timestamps.
* **Smart Background DB Logging:** A completely non-blocking, thread-safe background queue that logs every request into an SQLite database (`api_metrics_logs.db`), capturing input metadata, response times, HTTP statuses, and exceptions.
* **Custom Intelligent Middleware:** Tracks full lifecycle of requests, injecting 8-character hashed `request_id`s, capturing metadata safely without buffering large payloads, and calculating precise sub-millisecond execution times.
* **Disk Space Management Endpoint:** A built-in protected admin endpoint to delete obsolete logs and natively release hard drive storage space using SQLite's `VACUUM`.

## ⚠️ Technical Limitations
* `audio_url` is currently defined in models but not yet implemented (service relies exclusively on `audio_path`).
* Requires valid local access to orchestrator audio pathways (shared volume/mount) when operated inside a Docker container.
* Heavy reliance on system-level `ffmpeg`. Must be correctly installed and added to the environment's PATH.
* Synchronous external transcription calls: Re-transcription attempts are blocking; though implemented with jitter and backoff, heavy loads rely strictly on the external API rate limits.

---

## 📚 API Endpoints

### 1. Transcribe Segments
* **Method:** `POST`
* **Endpoint:** `/transcribe`
* **Description:** Main transcription pipeline. Receives target segments, slices the audio, and returns text for each segment.
* **Payload Example:**
    ```json
    {
      "audio_path": "/data/calls/call_001.wav",
      "segments": [
        {
          "speaker": "customer",
          "start": "00:00",
          "end": "00:05"
        }
      ]
    }
    ```

### 2. Service Health
* **Method:** `GET`
* **Endpoint:** `/health`
* **Description:** Liveness probe.

### 3. Purge Database Logs (Admin)
* **Method:** `DELETE`
* **Endpoint:** `/admin/logs/purge?days={number}`
* **Headers:** `x-api-key: {Your_ADMIN_SECRET_KEY}`
* **Description:** Deletes logs older than the specified `days` from the SQLite database and executes a `VACUUM` command to reclaim OS disk space.

---

## 🗄️ SQLite Database Schema (`api_metrics_logs.db`)
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

---
## 📂 Project Structure
```
STT_Online/
│ 
├── app/
│   ├── main.py              # Application factory, routing, and exception handlers
│   ├── config.py            # Pydantic settings & env management
│   ├── database_logger.py   # SQLite background thread and DB orchestration
│   ├── exceptions.py        # Custom App exceptions
│   ├── logger.py            # Loguru configuration (Terminal & JSONL file logs)
│   ├── middlewares.py       # Custom smart HTTP middleware for DB logging & timers
│   ├── models.py            # Pydantic schemas for request/response payloads
│   ├── request_context.py   # Context variables (request_id)
│   ├── transcriber.py       # Gateway to external STT API logic
│   └── utils.py             # System-level utility functions (ffmpeg wrappers)
├── logs/
│   ├── app.jsonl            # Loguru flat-file logs
│   └── api_metrics_logs.db  # Intelligent SQLite relational log storage
├── .env                     # Configuration variables
└── README.md                # Project documentation
```

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.9+
- `ffmpeg` installed on the host system.

### 2. Environment Variables (`.env`)
Create a `.env` file based on your `config.py`:
```env
GAPGPT_API_KEY=your_api_key_here
WHISPER_MODEL=whisper-1
GAPGPT_MAX_RETRIES=5
GAPGPT_RETRY_BASE_DELAY_SEC=1.5
GAPGPT_RETRY_MAX_DELAY_SEC=60
ADMIN_SECRET_KEY=super_secret_admin_key
```
### 3. Run the Server
```Bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
