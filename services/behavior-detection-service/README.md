# 🚀 Operator Behavior Detection Service

This is a FastAPI-based microservice designed to analyze and detect operator behaviors from transcripts using Large Language Models (LLMs). The service extracts operator speech and concurrently processes behaviors such as greetings, introductions, formal tone, and survey invitations.

---

## ✨ Key Features

* **🧠 Behavior Analysis**: Concurrently evaluates operator transcripts for multiple behavioral patterns using an LLM.
* **🗄️ Non-blocking Database Logging System**: Includes a highly optimized, background-thread SQLite logging system integrated directly into the `RequestIDMiddleware`. It strictly monitors API requests, calculates metrics (response times, statuses), safely handles binary input metadata, and stores error tracebacks, all without adding latency to the main API responses.
* **🛡️ Admin Purge Engine**: Secure endpoint to maintain database health by deleting old logs and executing `VACUUM` to free up disk space.

---

## ⚠️ Technical Limitations

* **🌊 Streaming Constraints**: Due to the background database logging middleware, extremely large synchronous payloads may require memory buffering. However, binary files are safely ignored and stored as metadata JSONs to prevent memory overflow.
* **⚡ SQLite Concurrency**: SQLite is utilized for logging. While the implementation uses a thread-safe queue to manage writes, it is best suited for small to medium-scale API traffic.
* **🤖 LLM Dependency**: The application heavily relies on an external LLM via `LLMClient`. The API's response time is directly proportional to the LLM's latency.

---

## 🌐 API Endpoints

### 🎯 1. Main Endpoints
* `POST /api/v1/detect`: Main endpoint to evaluate operator behaviors from transcript payloads. 
* `GET /health`: Basic health check.
* `GET /health/llm`: Health check specifically for testing the connection to the LLM.

### 🔒 2. Admin Endpoints
* `DELETE /admin/logs/purge`: Deletes logs older than the specified `days`. 
  * **Headers**: `x-api-key: <ADMIN_SECRET_KEY>`
  * **Query Parameters**: `days` (integer)

---

## 📊 SQLite Database Schema

The logging database is located at `log/api_metrics_logs.db`. The core table is `api_logs`:

| Column | Type    | Description |
| :--- |:--------| :--- |
| `id` | INTEGER | Primary Key (Auto-increment) |
| `request_id` | TEXT    | 8-character hashed unique request ID |
| `endpoint` | TEXT    | API route path accessed |
| `method` |  TEXT | HTTP Method (GET, POST, etc.) |
| `status_code`| INTEGER | HTTP Response code (e.g., 200, 500) |
| `request_time`| TEXT    | ISO format timestamp of the request |
| `response_time_sec`| REAL    | Exact execution time of the request in seconds |
| `input_data` | TEXT    | Body JSON or metadata (for binary payloads) |
| `output_data`| TEXT    | Basic response metadata |
| `error_message`|  TEXT   | Traceback or Validation error messages |
| `log_level` |  TEXT | INFO, ERROR (4xx+), CRITICAL (5xx) |

---
## 📂 Project Structure
```
Behavior_Detection/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── detect.py           # 🎯 Core detection routes
│   ├── core/
│   │   ├── database_logger.py      # 🗄️ SQLite Background worker & Purge logic
│   │   ├── errors.py
│   │   └── logging.py
│   ├── detection/                  # 🔍 Behavior detectors (Greeting, Tone, etc.)
│   ├── domain/                     # 📦 Pydantic models & Schemas
│   ├── llm/                        # 🤖 External LLM Client
│   ├── preprocessing/              # 🧹 Transcript filtering logic
│   └── utils/
│       └── request_id.py           # ⚡ Non-blocking smart logging middleware
├── log/
│   └── api_metrics_logs.db         # 🗃️ Auto-generated SQLite Database
├── main.py                         # 🚀 FastAPI Application Entrypoint
└── README.md                       # 📖 Project Documentation
```

## 🚀 Quick Start

### 🔐 1. Environment Variables (`.env`)
Create a `.env` file in the root directory and add your secret key:
```env
ADMIN_SECRET_KEY=your_secure_admin_key_here
```
### 💻 2. Run the Application
Make sure your virtual environment is active and run the following command:

```Bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
