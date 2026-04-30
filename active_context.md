# AuditBot Project Context

## 🎯 Project Vision
An automated, multi-tenant AI agent that watches Google Drive folders, parses invoices using MinerU, extracts structured data via any major LLM (Claude, GPT, Gemini), and saves results to Google Sheets and a PostgreSQL state store.

## 💻 Tech Stack
- **Language**: Python 3.12 (Downgraded from 3.13 for `pycocotools`/MinerU compatibility)
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
8.  **Processing Pipeline**: ✅ Headless LibreOffice conversion and MinerU PDF-to-Markdown integrated.
9.  **AI Validation**: ✅ Pydantic schema injection into LLM prompts guarantees structured output.
10. **Google Sheets Storing**: ✅ Generates an `output` subfolder and securely deposits spreadsheet rows per user.
11. **True Multi-Tenancy**: ✅ Users provide their specific folder ID during CLI registration, eliminating global `.env` dependencies.

12. **MinerU Integration Fixed**: ✅ Upgraded code to use the modern `magic-pdf` v1.3.12 API (`PymuDocDataset`, `doc_analyze`).
13. **MinerU Environment Setup**: ✅ Configured `magic-pdf.json` to use `doclayout_yolo` (bypassing tricky `detectron2` installs on Windows), injected it into the Docker build process, and successfully downloaded the 5GB HuggingFace models (`opendatalab/pdf-extract-kit-1.0`).

## 🚀 Immediate Next Steps (To-Do)
- [ ] **End-to-End Testing**: Run the full pipeline (upload document -> watcher -> consumer -> AI extraction -> Google Sheets) and confirm text extraction from MinerU outputs correctly to Sheets.
- [ ] **Restart Failed Jobs**: Run `UPDATE public.invoice_jobs SET retry_count = 0, status = 'NEW', error_message = NULL WHERE status = 'FAILED';` to retry the failed test files with the newly functioning MinerU setup.

## ⚠️ Known Gotchas / Troubleshooting
- **MinerU Model Weights**: MinerU requires ~5GB of model weights pulled from HuggingFace to function. This is handled via `huggingface_hub` in the setup script and Dockerfile.
- **MinerU Layout Model**: On Windows, we explicitly configure `magic-pdf.json` to use `doclayout_yolo` instead of `layoutlmv3` to avoid C++ `detectron2` compilation errors.
- **Image Writing**: MinerU uses a `DummyWriter` in `processor.py` to discard cropped images into memory since we only care about the Markdown layout for LLM extraction, saving disk space.

## 💡 Key Decisions
- **Master Switch**: The `AI_PROVIDER` env variable acts as the single control point for switching AI platforms at runtime.
- **Platform Agnosticism**: Factory pattern allows seamless switching between LLM providers via `.env`.
- **State Store**: PostgreSQL is the source of truth for both credentials and job states to ensure **Idempotency**.
- **Isolation**: strict `user_email` based isolation for multi-tenant security and privacy.
