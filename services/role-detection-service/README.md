# 🎙️Role Detection Microservice 

A lightweight, standalone FastAPI microservice designed to ingest speech segments from an audio call and intelligently identify the **Operator** and the **Customer** using both temporal analysis (e.g., talk time, turns) and NLP pattern matching (e.g., standard operator greetings).

## 🌟 Key Features

* **Hybrid Role Detection Logic:** Uses a combination of acoustic/time metrics (longest speech time, first to speak) and language-based rules (custom keywords and formal patterns) to pinpoint the operator accurately.
* **High-Performance DB Logging (Non-blocking):** A custom background-threaded SQLite logger seamlessly tracks request inputs, execution time, and status codes without blocking the API's main async event loop.
* **Smart Payload Handling:** Extracts metadata from large binary files/streams to prevent the database from bloating, gracefully saving JSON structures.
* **Built-in Log Management:** A secured endpoint (`/admin/logs/purge`) that completely frees up disk space via SQLite `VACUUM` when deleting old logs.
* **Comprehensive Error Tracking:** Fully equipped to catch unhandled exceptions, validation errors (422), and standard HTTP errors, storing detailed stack traces and messages securely in the DB.

## ⚠️ Technical Limitations

* **Transcription Dependency:** The accuracy of the content-based scoring relies heavily on the quality of the Speech-To-Text (STT) outputs provided in the `text` attribute.
* **Language Specificity:** Currently optimized for Persian/Farsi dialects using specific hardcoded keywords and `normalize_fa` function. Modifying the `OPERATOR_KEYWORDS` list is necessary for other languages.
* **SQLite Concurrency:** SQLite is well-suited for light-to-moderate analytics. For deployments handling thousands of concurrent requests per second, migrating the logging component to PostgreSQL or Redis is recommended.

## 🌐 API Endpoints

### 1. `GET /health`
Checks the heartbeat and operational status of the service.

### 2. `POST /detect`
The primary endpoint. Accepts an array of transcribed segments and returns the identified `operator_id`, `customer_id`, and precise speaking metrics.
* **Body Example:** `{"segments": [{"speaker": "SPEAKER_01", "start": 0.5, "end": 2.5, "text": "سلام وقت بخیر"}]}`

### 3. `DELETE /admin/logs/purge` (Admin Only)
Purges database logs older than the specified limit and executes `VACUUM` to reclaim disk space.
* **Query Params:** `days` (integer, default: 30)
* **Headers:** `x-api-key` (Must match the environment variable)


## 🗄️ SQLite Database Schema (`api_metrics_logs.db`)

Stored in the `log/` directory, the `api_logs` table logs all traffic metrics.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key (Autoincrement). |
| `request_id` | TEXT | 8-character hashed ID unique to the request. |
| `endpoint` | TEXT | API endpoint path (e.g., `/detect`). |
| `method` | TEXT | HTTP Method (GET, POST, DELETE). |
| `status_code` | INTEGER | HTTP response status (e.g., 200, 422, 500). |
| `request_time` | DATETIME | Timestamp of when the request arrived. |
| `response_time_sec` | REAL | Total processing time in seconds. |
| `input_data` | TEXT | JSON representation of payload or stream metadata. |
| `output_data` | TEXT | JSON response status summary. |
| `error_message` | TEXT | Captures traceback for 500s or Validation Error details. |
| `log_level` | TEXT | Severity flag (`INFO`, `WARNING`, `ERROR`, `CRITICAL`). |

## 📁 Project Structure
```
Role_Detection/
│
├── main.py                   # FastAPI Application, endpoints, middleware, and logic
├── database_logger.py        # Background SQLite logger and purge operations
├── log/                      
│   └── api_metrics_logs.db   # Auto-generated SQLite database (creates on first run)
├── README.md                 # Project Documentation
└── requirements.txt          # Python dependencies
```

## 🚀 Quick Start

### 1. Set Environment Variables
Create a `.env` file in the root directory (or export directly in your terminal) to set your secure Admin Secret Key:
```bash
export ADMIN_SECRET_KEY="your-secure-custom-key"
```
### 2. Install Dependencies
Ensure you have the required packages installed:
```Bash
pip install fastapi uvicorn pydantic python-dotenv
```
### 3. Run the Server
Boot up the microservice using Uvicorn:

```Bash
uvicorn main:app --host 0.0.0.0 --port 8005
```
