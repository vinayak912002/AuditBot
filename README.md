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

## 🛠️ Setup

### 1. Environment
Create a Conda environment and install dependencies:
```bash
conda create -n AuditBot python=3.13
conda activate AuditBot
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file based on `.env.example`:
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: Obtain from Google Cloud Console (OAuth 2.0 Client IDs).
- `ANTHROPIC_API_KEY`: For Claude-based extraction.
- `DATABASE_URL`: Connection string for your PostgreSQL instance.

### 3. Database Initialization
```bash
python main.py --init-db
```

### 4. User Registration
To authorize a Google Drive account:
```bash
python -m src.watcher.drive_watcher --register
```

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
