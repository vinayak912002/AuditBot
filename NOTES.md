# AuditBot: Long-Term Project Notes & Architecture Guide

## 🌟 Project Overview
AuditBot is a robust, multi-tenant automation system designed to bridge the gap between unstructured invoice data (PDFs/Images) in Google Drive and structured accounting systems. It was built with a focus on **Idempotency** (never processing the same file twice) and **Reliability** (resuming seamlessly after crashes).

---

## 🏗️ Core Architecture

The system is split into two independent services that communicate via a PostgreSQL database. This "Producer-Consumer" pattern allows the system to scale easily.

### 1. The Watcher (`src.watcher.drive_watcher`)
*   **Role**: The "Scout."
*   **Action**: Polls specific Google Drive folders for every registered user.
*   **Logic**: When it finds a file, it checks the database. If the `file_id` doesn't exist, it creates a new entry with the status `NEW`.
*   **Authentication**: Uses OAuth2 "Desktop Flow." Tokens are stored in the database and automatically refreshed using `refresh_tokens`.

### 2. The Consumer (`src.consumer.processor`)
*   **Role**: The "Worker."
*   **Action**: Looks for jobs in the database with status `NEW` or `FAILED`.
*   **Pipeline**:
    1.  **Normalization**: Downloads the file from Google Drive.
    2.  **Parsing (MinerU)**: Converts the PDF/Image into clean Markdown/Text.
    3.  **Extraction (AI)**: Sends the text to an LLM (Gemini/Claude/GPT) to get structured JSON (Vendor, Date, Amount, etc.).
    4.  **Storing**: (Planned) Saves the results to a Google Sheet.

---

## 🔐 Data & Security
*   **Multi-Tenancy**: Every job and credential is tied to a `user_email`. The system is designed to handle hundreds of different users' drives simultaneously without data leakage.
*   **State Machine**: Jobs move through states: `NEW` -> `PROCESSING` -> `PROCESSED` or `FAILED`.
*   **Atomic Locking**: The Consumer uses `SELECT ... FOR UPDATE SKIP LOCKED`. This is a professional-grade database technique that allows you to run multiple Consumers at once without them ever fighting over the same job.

---

## 🛠️ Key Technologies
*   **Python 3.13**: Using the latest features and performance improvements.
*   **PostgreSQL**: Chosen for its "ACID" compliance, ensuring that your job states are never corrupted.
*   **MinerU (`magic-pdf`)**: A specialized tool for high-fidelity parsing of complex, multi-column PDFs.
*   **AI Factory Pattern**: The code is "Agnostic." You can switch between Google Gemini, Anthropic Claude, and OpenAI GPT just by changing one variable in your `.env` file.

---

## 💡 Troubleshooting & Common Issues (Learned during Dev)
*   **Module Resolution**: Always run the project using `python -m src.path.to.module` from the root directory. This ensures all internal imports work correctly.
*   **Google OAuth Scopes**: If you get a "Scope Changed" error, it's usually because the `openid` scope was added by Google. We use `OAUTHLIB_RELAX_TOKEN_SCOPE=1` to handle this.
*   **Sensitive Scopes**: When registering a new user, you **must** manually check the box on the Google consent screen to allow Drive access; otherwise, the bot will be "blind."

---

## 🚀 Future Roadmap
*   **MinerU Integration**: Replace the current mock parser with the actual `magic-pdf` library.
*   **Google Sheets Integration**: Automatically append extracted data to the user's specific spreadsheet.
*   **Pydantic Validation**: Ensure the JSON returned by the AI matches a strict schema before saving it.
*   **AWS Deployment**: Move to ECS Fargate for a 24/7 serverless operation.

---

*Notes last updated: April 2026*
