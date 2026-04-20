# Testing Guide: AuditBot

This guide outlines how to verify the functionality, reliability, and platform-agnostic AI logic of AuditBot.

## 🧪 Prerequisites
- A Google Cloud Project with the **Drive API** enabled and an OAuth2 Client ID.
- **Anthropic API Key** (for Claude testing).
- **OpenAI API Key** (for GPT-4o testing).
- **Gemini API Key** (for Gemini testing).
- PostgreSQL (Local or Docker Desktop).

---

## 1. Local Testing (Native Python)

### Step A: Database & Environment
1. Start your local Postgres and run migrations: `python main.py --init-db`.
2. Verify tables `user_credentials` and `invoice_jobs` are created.

### Step B: User Authorization
1. Run `python -m src.watcher.drive_watcher --register`.
2. Follow the browser link to authorize your Google Drive account.
3. **Verification**: Check the `user_credentials` table in Postgres for a new record.

### Step C: The Happy Path
1. Upload a sample invoice (PDF or Image) to your watched Google Drive folder.
2. Start the watcher: `python -m src.watcher.drive_watcher`.
3. **Verification**: A new row should appear in `invoice_jobs` with status `NEW`.
4. Start the consumer: `python -m src.consumer.processor`.
5. **Verification**: The logs will show the 4-step pipeline executing. Check the `extracted_data` JSON column in the database once the status reaches `PROCESSED`.

---

## 2. Testing AI Platform Agnosticism

The `AI_PROVIDER` environment variable in your `.env` is the **master switch**. Whichever platform you set there will be the one the service uses for all extraction tasks.

### Test 1: Anthropic (Claude)
1. In your `.env`, set: `AI_PROVIDER=anthropic`.
2. **Default Model**: `claude-3-5-sonnet-20240620`.
3. **Override Model**: Set `ANTHROPIC_MODEL=claude-3-haiku-20240307`.
4. **Verify**: Logs show `Extraction using anthropic`.

### Test 2: OpenAI (GPT)
1. In your `.env`, set: `AI_PROVIDER=openai`.
2. **Default Model**: `gpt-4o`.
3. **Override Model**: Set `OPENAI_MODEL=gpt-3.5-turbo`.
4. **Verify**: Logs show `Extraction using openai`.

### Test 3: Google (Gemini)
1. In your `.env`, set: `AI_PROVIDER=gemini`.
2. **Default Model**: `gemini-1.5-pro`.
3. **Override Model**: Set `GEMINI_MODEL=gemini-1.5-flash`.
4. **Note**: Models earlier than Gemini 1.5 may not support the native JSON mode and might require prompt adjustments.
5. **Verify**: Logs show `Extraction using gemini`.

---

## 3. High-Reliability Scenarios

### Scenario 1: Idempotency (Process Interruption)
1. While the consumer is in the middle of processing (e.g., during the "Extraction" step), kill the process (`Ctrl+C`).
2. The job will remain in the `PROCESSING` state.
3. Restart the consumer. The job will eventually be retried, ensuring no data loss.

### Scenario 2: Error Handling & Retries
1. Provide an invalid API key in `.env`.
2. **Expected Result**: The job status moves to `FAILED`, the `retry_count` increments, and the specific error from the AI provider is saved in the `error_message` column.

---

## 4. Docker Desktop Testing
1. Run `docker-compose up --build`.
2. Monitor service logs:
   ```bash
   docker logs -f auditbot-watcher-1
   docker logs -f auditbot-consumer-1
   ```
3. To register a new user while inside Docker:
   ```bash
   docker exec -it auditbot-watcher-1 python -m src.watcher.drive_watcher --register
   ```
