<div align="center">

# 🎼 Call Center Orchestrator API

*The central nervous system for advanced audio analysis pipelines.*

---
</div>

Welcome to the **Call Center Orchestrator API**. This high-performance, asynchronous FastAPI application acts as the central hub for automating complex audio workflows, seamlessly connecting raw audio files to deep analytical microservices.

## ✨ Key Features

* ⚡ **Full Audio Pipeline:** Automates the complete journey from raw call audio to Transcription, Silence Detection, Overlap Analysis, Behavior Detection, Sentiment Analysis, and Operator Scoring.
* 🧠 **Smart Audio Processing:** Integrates FFmpeg utilities to flawlessly manage duration extraction, audio chunking, and formatting.
* 🛡️ **Resilient Microservice Orchestration:** Communicates with external ML models using robust, timeout-aware asynchronous HTTP clients with built-in retry logic.
* 📊 **Non-Blocking Background Logging:** Features a truly asynchronous SQLite database logging engine. It captures request metrics (duration, status, payload metadata) without adding a single millisecond of latency to API response times.
* 🧹 **Automated Log Maintenance:** Built-in, API-key-protected endpoint to effortlessly purge stale logs and execute `VACUUM` to keep disk usage strictly optimized.

---

## 🧩 System Architecture

The project follows a microservice-based architecture. Each AI capability is implemented as an independent HTTP API service, while the Orchestrator coordinates the full workflow.

## 🤖 AI Microservices

| Microservice | Responsibility | Input | Output |
| :--- | :--- | :--- | :--- |
| **Diarization Service** | Detects and separates speakers in the audio file. | Audio file | Speaker-labeled time segments |
| **STT Service** | Converts spoken audio into text. | Audio file or segments | Transcript |
| **Role Detection Service** | Identifies the role of each speaker, such as customer or operator. | Transcript + speaker segments | Role-labeled transcript |
| **Silence Analysis Service** | Calculates silence duration, silence intervals, and silence ratio, especially for the operator. | Audio or segments | Silence metrics |
| **Overlap Detection Service** | Detects time periods where multiple speakers talk simultaneously. | Audio file | Overlap intervals and durations |
| **Behavior Detection Service** | Detects predefined operational or conversational behaviors from the transcript. | Transcript | Behavior labels or scores |
| **Sentiment Analysis Service** | Analyzes the customer’s emotional tone and sentiment during the call. | Customer utterances | Sentiment label or score |
| **Operator Scoring Service** | Evaluates operator performance based on politeness, anger control, and problem-solving quality. | Transcript + analysis results | Operator score |
| **Orchestrator API** | Coordinates all AI services and exposes unified pipeline endpoints. | Audio file | Structured JSON analysis result |

---

## ⚠️ Technical Limitations

> **Note:** Please consider the following constraints before deploying to production.

* **Audio Formats:** Only `.mp3`, `.m4a`, and `.wav` extensions are supported.
* **Heavy Payload Handling:** To protect the database size, the background logger strictly avoids storing binary audio data. It computes and logs only metadata (e.g., `size_mb`, `content_type`).
* **External Dependencies:** The orchestrator relies heavily on downstream AI microservices. If these services fail to respond within timeout limits, a custom `502/503` exception is raised safely.
* **System Requirements:** The host OS **must** have `ffmpeg` and `ffprobe` installed and accessible via system PATH.

## 🌐 API Endpoints

### 🔬 Core Pipelines
*All core pipelines require a `multipart/form-data` payload containing a `file` field.*

* **`POST`** `/pipeline/transcription` — Runs Diarization, STT, and Role Detection.
* **`POST`** `/pipeline/operator-silence` — Calculates agent silence metrics and ratios.
* **`POST`** `/pipeline/behavior` — Analyzes transcripts for specific operational behaviors.
* **`POST`** `/pipeline/sentiment` — Isolates customer utterances to assess call sentiment.
* **`POST`** `/pipeline/operator-score` — Evaluates politeness, anger control, and problem-solving skills.
* **`POST`** `/pipeline/overlap` — Detects and times blocks where multiple speakers talk simultaneously.

### 🛠️ Admin Tools

* **`DELETE`** `/admin/logs/purge`
    * **Query Params:** `days` (Default: `30`)
    * **Headers:** `x-api-key: <ADMIN_SECRET_KEY>`
    * **Action:** Securely deletes database logs older than the specified days and executes a database `VACUUM`.

---

---

## 🗄️ SQLite Database Schema

The API metrics are stored in an internally managed `api_logs` table (auto-created in the `/logs` directory).

| Column | Data Type | Description |
| :--- | :--- | :--- |
| **`id`** | `INTEGER` | Primary Key (Auto-incremented). |
| **`request_id`** | `TEXT` | An 8-character hashed unique identifier per request. |
| **`endpoint`** | `TEXT` | The exact path requested (e.g., `/pipeline/behavior`). |
| **`method`** | `TEXT` | HTTP Method used (`POST`, `DELETE`, etc.). |
| **`status_code`**| `INTEGER` | Final HTTP Status Code (e.g., `200`, `422`, `500`). |
| **`request_time`**| `TEXT` | UTC timestamp in ISO 8601 format. |
| **`response_time_sec`**| `REAL` | Total time taken to process the request (in seconds). |
| **`input_data`** | `TEXT` | Input JSON string or intelligent file metadata. |
| **`output_data`**| `TEXT` | Minimal output status representation. |
| **`error_message`**| `TEXT` | Detailed exception trace for Unhandled/Validation errors. |
| **`log_level`** | `TEXT` | Severity level (`INFO`, `ERROR`, or `CRITICAL`). |

---

## 📂 Project Structure
```
 📦 call-center-ai-orchestrator
 ┣ 📂 orchestrator/                  # Central FastAPI orchestration service
 ┃ ┣ 📜 main.py
 ┃ ┣ 📜 config.py
 ┃ ┣ 📜 clients.py
 ┃ ┣ 📜 database_logger.py
 ┃ ┣ 📜 exceptions.py
 ┃ ┣ 📜 logger.py
 ┃ ┣ 📜 schemas.py
 ┃ ┣ 📜 utils.py
 ┃ ┣ 📜 README.md
 ┃ ┗ 📂 logs/
 ┣ 📂 services/                      # Independent AI microservices
 ┃ ┣ 📂 diarization-service/
 ┃ ┣ 📂 stt-service/
 ┃ ┣ 📂 role-detection-service/
 ┃ ┣ 📂 silence-analysis-service/
 ┃ ┣ 📂 overlap-detection-service/
 ┃ ┣ 📂 behavior-detection-service/
 ┃ ┣ 📂 sentiment-analysis-service/
 ┃ ┗ 📂 operator-scoring-service/
 ┣ 📜 docker-compose.yml
 ┣ 📜 .env
 ┣ 📜 .gitignore
 ┗ 📜 README.md
```

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have Python 3.10+ and FFmpeg installed on your machine.
```bash
# Ubuntu/Debian example for FFmpeg
sudo apt update && sudo apt install ffmpeg
```
### 2. Environment Setup
Create a `.env` file in the root directory and configure your microservice URLs and Security 
* Keys:
```
DIARIZATION_URL=http://your-diarize-service/api
ROLE_DETECTION_URL=http://your-role-service/api
STT_URL=http://your-stt-service/api
SILENCE_FROM_SEGMENTS_URL=http://your-silence-service/api
OVERLAP_URL=http://your-overlap-service/api
BEHAVIOR_URL=http://your-behavior-service/api
SENTIMENT_URL=http://your-sentiment-service/api
OPERATOR_SCORE_URL=http://your-scoring-service/api
```
* Security & Admin
```
ADMIN_SECRET_KEY=super-secret-admin-key-replace-me
```
### 3. Launch the Application
Install dependencies and run the server using Uvicorn:
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
