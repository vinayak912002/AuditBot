# AuditBot Project Context

## 🎯 Project Vision
An automated, multi-tenant AI agent that watches Google Drive folders, parses invoices using MinerU, extracts structured data via any major LLM (Claude, GPT, Gemini), and saves results to Google Sheets and a PostgreSQL state store.

## 💻 Tech Stack
- **Language**: Python 3.13
- **Database**: PostgreSQL (Source of truth for jobs and user credentials)
- **ORM**: SQLAlchemy
- **APIs**: Google Drive (OAuth2), Anthropic (Claude), OpenAI (GPT-4), Google Gemini (Generative AI)
- **Parsing**: MinerU (`magic-pdf`)

## 📂 Current Architecture
- `src/database/models.py`: Defines `UserCredential` and `InvoiceJob` with atomic states.
- `src/watcher/drive_watcher.py`: Multi-user polling with OAuth2 and DB-backed token storage.
- `src/consumer/ai_providers.py`: **Agnostic AI Layer** supporting Anthropic, OpenAI, and Gemini with dynamic model selection.
- `src/consumer/processor.py`: The worker loop with a 4-step pipeline and atomic job locking.

## 📍 Current Progress
1.  **Identity & Auth**: ✅ Multi-user OAuth2 storage in DB implemented.
2.  **Job Tracking**: ✅ Atomic state machine in Postgres implemented.
3.  **Drive Monitoring**: ✅ Polling logic for multiple accounts implemented.
4.  **AI Agnosticism**: ✅ Factory pattern for switching between **Claude, GPT-4o, and Gemini** implemented.
5.  **Model Flexibility**: ✅ Support for custom model strings (e.g., Flash, Haiku) via environment variables.
6.  **Gemini Testing**: ✅ Extraction logic (Step 3/4) verified using Gemini Flash. Confirmation that the AI integration is working even while MinerU parsing is still a placeholder.
7.  **Full Documentation**: ✅ Completed `README.md`, `testing.md`, and `active_context.md`.
8.  **Processing Pipeline**: 🚧 Skeleton implemented; MinerU and Sheets integration pending.

## 🚀 Immediate Next Steps (To-Do)
1.  **Fix Deprecations**: 
    - Replace `datetime.utcnow()` with `datetime.now(datetime.UTC)` in `processor.py`.
    - Migrate Gemini SDK from `google-generativeai` to `google-genai`.
2.  **Integrate MinerU**: In `src/consumer/processor.py`, replace `_parse_with_mineru` placeholder with actual `magic-pdf` calls.
3.  **Google Sheets Storing**: Implement the `Storing` step in the consumer to append `extracted_data` to a user-specific Google Sheet.
4.  **Validation Logic**: Implement Pydantic models to validate the JSON returned by the AI providers.

## ⚠️ Deprecation Warnings
- **Google Gemini SDK**: Support for the `google.generativeai` package has ended. It will no longer be receiving updates or bug fixes. The project needs to switch to the `google.genai` package as soon as possible.

## 💡 Key Decisions
- **Master Switch**: The `AI_PROVIDER` env variable acts as the single control point for switching AI platforms at runtime.
- **Platform Agnosticism**: Factory pattern allows seamless switching between LLM providers via `.env`.
- **State Store**: PostgreSQL is the source of truth for both credentials and job states to ensure **Idempotency**.
- **Isolation**: strict `user_email` based isolation for multi-tenant security and privacy.
