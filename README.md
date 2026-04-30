# AuditBot: AI-Powered Invoice Automation

AuditBot is an automated system designed for tax firms to detect, process, and extract data from invoices stored in Google Drive. It uses MinerU for high-fidelity document parsing and high-performance LLMs for intelligent data extraction.

## 🚀 Features
- **Multi-User Support**: Individual OAuth2 authentication and data isolation for multiple Google accounts.
- **Atomic Job Processing**: Uses PostgreSQL as a state store to ensure jobs are never lost or double-processed.
- **MinerU Integration**: High-quality PDF-to-Markdown parsing.
- **Idempotent Design**: Resumes exactly where it left off after a system crash or restart.
- **Platform Agnostic AI**: Support for Anthropic, OpenAI, and Google Gemini.
- **Python 3.13**: Optimized for the latest Python runtime.
- **Structured Logging**: Detailed tracking of every stage (Normalization, Parsing, AI Extraction, Storing).

## 🏗️ Architecture & Design Decisions

### 1. The State Machine
Jobs transition through four specific states in PostgreSQL:
`NEW` ➔ `PROCESSING` ➔ `PROCESSED` (or `FAILED`)
- **Decision**: We chose PostgreSQL as the source of truth rather than an in-memory queue to ensure 100% data durability.

### 2. Concurrency & Atomicity
- **Decision**: The Consumer uses `SELECT ... FOR UPDATE SKIP LOCKED`. This allows multiple consumer instances to run in parallel without ever picking up the same invoice.

### 3. OAuth2 & Multi-Tenancy
- **Decision**: Credentials (including refresh tokens) are stored in the `user_credentials` table. This allows the service to scale across multiple clients/users while maintaining strict data isolation.

### 4. 4-Step Processing Pipeline
1. **Normalization**: Downloading and standardizing the file.
2. **Parsing (MinerU)**: Converting complex PDFs into clean text.
3. **Extraction (AI)**: Using LLM Vision/Text capabilities for structured data.
4. **Storing**: Finalizing the record in the DB and potentially external sheets.

### 5. AI Model Flexibility
AuditBot uses a **Factory Pattern** for AI providers. While the system defaults to high-performance models (`claude-3-5-sonnet`, `gpt-4o`, `gemini-1.5-pro`), **all model variants from these providers are supported**. You can override the default by setting the appropriate model variable in your `.env`.

> **Note**: Gemini 1.5 is the recommended default for Google because it supports native JSON schema constraints.

## ☁️ Deployment to AWS

For a production deployment on AWS, the following stack is recommended:

### 1. Database (Amazon RDS)
- Use **Amazon RDS for PostgreSQL**.
- Ensure the Security Group allows traffic on port 5432 from the ECS service.

### 2. Compute (Amazon ECS with Fargate)
- Create an ECS Cluster.
- Define two **Task Definitions**:
    - **Watcher Task**: Runs `python -m src.watcher.drive_watcher`.
    - **Consumer Task**: Runs `python -m src.consumer.processor`.
- Use **Fargate** to run these containers serverlessly.

### 3. Secrets Management (AWS Secrets Manager)
- Store `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, and `GOOGLE_CLIENT_SECRET` in Secrets Manager.
- Map these secrets to environment variables in your ECS Task Definitions.

### 4. Storage (Amazon EFS - Optional)
- If using MinerU's local caching or temporary file processing, mount an **Amazon EFS** volume to your ECS tasks for persistent scratch space.

## 🛠️ Setup Instructions

### Option A: Local Setup

**1. System Dependencies**
AuditBot requires headless LibreOffice and MinerU system dependencies to convert and parse documents.
- **Ubuntu/Debian**: `sudo apt-get install libreoffice libgl1 libglib2.0-0`
- **MacOS**: `brew install --cask libreoffice`
- **Windows**: 
  1. Download and install [LibreOffice for Windows](https://www.libreoffice.org/download/download-libreoffice/).
  2. Add the installation directory (usually `C:\Program Files\LibreOffice\program`) to your Windows System `PATH` environment variable. This ensures the `soffice` command is globally available.

**2. MinerU Configuration (Required)**
MinerU requires a configuration file named `magic-pdf.json` located in your user home directory (e.g., `C:\Users\YourUser\magic-pdf.json` or `~/magic-pdf.json`).
Create the file with the following minimum required structure. **On Windows**, ensure you set the layout model to `doclayout_yolo` to avoid complex `detectron2` compile errors:
```json
{
  "models-dir": "/tmp/models",
  "device-mode": "cpu",
  "table-config": {
    "model": "rapid_table",
    "enable": false,
    "max_time": 400
  },
  "layout-config": {
    "model": "doclayout_yolo"
  },
  "formula-config": {
    "mfd_model": "yolov8_mfd",
    "mfr_model": "unimernet_v2_small",
    "enable": false
  }
}
```
*(Note: Change `"models-dir"` to a valid local path on Windows like `C:/Users/YourUser/.mineru/models`)*

**3. Download AI Models (Required for MinerU)**
MinerU requires you to download the actual machine learning weights (roughly ~5GB) into the directory specified in your config (`C:/Users/YourUser/.mineru/models` or `/tmp/models`). 

You can download them automatically using Python:
```bash
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='opendatalab/pdf-extract-kit-1.0', local_dir='C:/Users/YourUser/.mineru/models')"
```
*(Make sure `local_dir` perfectly matches the `"models-dir"` in your `magic-pdf.json`)*

**4. Python Environment**
Create a Conda environment and install dependencies:
```bash
conda create -n AuditBot python=3.12
conda activate AuditBot
pip install -r requirements.txt
```

**5. Configuration & Database**
Create a `.env` file based on `.env.example`. Then initialize the database:
```bash
python main.py --init-db
```

### Option B: Docker Setup (Recommended)
Docker ensures all system dependencies (LibreOffice, libgl1) are automatically handled.

**1. Configuration**
Create a `.env` file based on `.env.example`. Set your `DATABASE_URL` to point to the dockerized postgres instance (e.g., `postgresql://postgres:postgresroot@db:5432/auditbot`).

**2. Build and Run**
```bash
docker-compose up --build -d
```
*Note: You must still run the User Registration flow interactively (see below) before the background containers will pick up files.*

---

### 👤 User Registration (Multi-Tenant)
AuditBot supports true multi-tenancy. Each user must authorize their Google account and link a specific Drive folder.

To authorize a Google Drive account:
```bash
python -m src.watcher.drive_watcher --register
```
1. A browser window will open for Google OAuth.
2. The CLI will then prompt you to enter the **Folder URL or ID** you want AuditBot to monitor.
3. AuditBot will automatically create an `output/` subfolder inside that location where the extracted spreadsheets will be securely deposited.

## 🏃 Running the Service

### Start the Watcher (Detects new files)
```bash
python -m src.watcher.drive_watcher
```

### Start the Consumer (Processes files)
```bash
python -m src.consumer.processor
```

## 📂 Project Structure
- `src/watcher/`: Logic for polling Google Drive.
- `src/consumer/`: Logic for MinerU parsing and AI extraction.
- `src/database/`: SQLAlchemy models and state management.
- `src/common/`: Shared database and logging utilities.
