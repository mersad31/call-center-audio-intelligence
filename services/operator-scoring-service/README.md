# 🎯 Operator Scoring Service 🚀

A high-performance, enterprise-grade FastAPI service engineered to automatically evaluate call center operator transcripts. By processing turn-by-turn conversation data, the system leverages advanced Gemini LLM reasoning to grade agent performance across critical customer service KPIs: **Politeness**, **Anger Control**, and **Problem Solving**. 

This service features a state-of-the-art, **fully non-blocking database logging and telemetry engine** running on SQLite.

---

## ⚡ Key Features

* **🧠 AI-Powered QA Grading:** Automatically parses conversation flows and extracts numeric behavioral metrics (0-100) based on targeted prompt compliance.
* **🚀 Blazing-Fast Asynchronous Logging:** Utilizes highly optimized `asyncio.create_task` and `asyncio.to_thread` architectures so that analytical database writes *never* block or delay client response times.
* **🛡️ Intelligent Stream & Payload Guard:** The custom middleware intercepts heavy form-data, multi-part assets, or binary structures to extract safe JSON structural metadata (size in MB, parameters) instead of clogging database space.
* **🔍 Centrally Intercepted Error Handlers:** Deep exception hooking structures capture Pydantic payload validation discrepancies (`ValidationError`), standard `HTTPExceptions`, and unhandled background code crashes alongside complete tracebacks.
* **🧹 Active Storage Defragmentation:** Exposes a secure administration purge interface that drops historical logs and safely executes an autonomous SQLite `VACUUM` to release free space to the OS.

## ⚠️ Technical Limitations
* **SQLite Concurrent Write Queues:** High-scale parallel systems could run into temporary write bottlenecks when the `VACUUM` command locks database allocations. Our engine bypasses transactions via `isolation_level=None` and extends connection timeout limits to 30.0 seconds to avoid drop-offs.

* **Data Sufficiency Perimeters:** Input requests containing fewer than 2 separate utterances are actively blocked before prompting to eliminate unnecessary upstream token expenditures.
# 🔌 API Endpoints
### 1. 🩺 Health Interception Check
* **URL:** `GET /health`

* **Auth Requirement:** None 🔓

* **Response Payload (200 OK):**
```JSON
{
  "status": "ok",
  "service": "operator_scoring_service"
}
```
### 2. 📊 Operator Evaluation Engine
* **URL:** `POST /score`

* **Auth Requirement:** None 🔓

* **Response Headers:** Appends `X-Request-ID` tracking hash to response parameters.

* **Request Payload Example:**

```JSON
{
  "conversation_id": "conv_2026_x1",
  "utterances": [
    {"speaker": "customer", "start_time": 0.0, "end_time": 3.5, "text": "سلام، من پنلم کار نمیکنه و واقعاً کارم لنگ مونده."},
    {"speaker": "operator", "start_time": 4.2, "end_time": 9.0, "text": "سلام وقت شما بخیر. عذرخواهی می‌کنم بابت مشکل پیش آمده، لطفاً کدملی ثبت‌نامی رو بفرمایید تا سریعاً براتون بررسی کنم."}
  ]
}
```
* **Success Response (200 OK):**
```JSON
{
  "politeness_score": 100,
  "anger_control_score": 100,
  "problem_solving_score": 95
}
```
### 3. 🧹 Administrative Maintenance Purge
* **URL:** `DELETE /admin/logs/purge`

* **Query Parameters:** `days` (Integer constraint threshold, default=30)

* **Headers Required:** `x-api-key`: `YOUR_ADMIN_SECRET_KEY`

* **Success Response (200 OK):**

```JSON
{
  "message": "Successfully purged 1520 logs older than 30 days."
}
```
* **Error Response (401 Unauthorized):**

```JSON
{
  "detail": "Unauthorized: Invalid API Key"
}
```
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

```text
.
├── 📂 app/
│   ├── 📄 __init__.py
│   ├── 📄 config.py             # ⚙️ Environment definitions & schema validation
│   ├── 📄 database_logger.py    # 📊 Non-blocking SQLite bridge & autocommit vacuum
│   ├── 📄 llm_client.py         # 🤖 Upstream OpenAI/Gemini connector client
│   ├── 📄 logging_config.py     # 📝 Standardized JSON system file logger
│   ├── 📄 main.py               # 🔌 App initialization, exception listeners & routes
│   ├── 📄 middleware.py         # 🛡️ Request-ID generator & safe payload handler
│   ├── 📄 schemas.py            # 📦 Pydantic structural contract definitions
│   └── 📄 scoring_prompt.py     # 📝 Strategic behavioral evaluation prompt
├── 📂 log/
│   └── 📄 api_metrics_logs.db   # 🗄️ Automatically generated metrics database
├── 📄 .env                      # 🔐 Application credentials and local variables
└── 📄 README.md                 # 📖 Comprehensive technical documentation
```
## ⚙️ Quick Start
### 1. 🔐 Configuration Blueprint
Configure a local production environment mapping template labeled `.env` in the root workspace directory:

```
GAPGPT_BASE_URL=[https://api.yourllmprovider.com/v1](https://api.yourllmprovider.com/v1)
GAPGPT_API_KEY=your_secret_upstream_llm_integration_key
MODEL_NAME=gemini-2.5-flash
ADMIN_SECRET_KEY=highly_secure_admin_passphrase_here
```
### 2. 🚀 Launching the Worker Process
Deploy dependencies and run the server loop using standard Uvicorn worker threads:

```Bash
# Ingest workspace setup requirements
pip install -r requirements.txt

# Run the core FastAPI engine
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```


