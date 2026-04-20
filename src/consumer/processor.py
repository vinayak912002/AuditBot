import os
import json
import logging
import io
import time
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from src.common.db import SessionLocal
from src.database.models import InvoiceJob, JobStatus, UserCredential
from src.consumer.ai_providers import get_ai_provider
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConsumerService:
    """
    Worker service that processes jobs found in the database.
    It transitions jobs through the state machine (NEW -> PROCESSING -> PROCESSED).
    """
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        # Platform agnostic AI client (factory pattern)
        self.ai_client = get_ai_provider()

    def _get_drive_service(self, user_email):
        """Builds a Drive service for a specific user using their stored credentials."""
        with SessionLocal() as db:
            user = db.query(UserCredential).filter_by(email=user_email).first()
            if not user:
                raise Exception(f"No credentials found for user {user_email}")
            creds = Credentials.from_authorized_user_info(user.token_data)
            return build('drive', 'v3', credentials=creds)

    def process_jobs(self):
        """
        The main worker loop.
        Continuously polls the DB for NEW or FAILED jobs and processes them.
        """
        logger.info(f"Consumer service started using provider: {os.getenv('AI_PROVIDER', 'anthropic')}")
        
        last_heartbeat = 0
        while True:
            # Show a heartbeat every 60 seconds to confirm the service is alive.
            if time.time() - last_heartbeat > 60:
                logger.info("Polling for new jobs...")
                last_heartbeat = time.time()

            db = SessionLocal()
            try:
                # ATOMIC LOCKING:
                # 1. find a job that is NEW or FAILED.
                # 2. 'with_for_update' locks the row so other consumers can't touch it.
                # 3. 'skip_locked=True' means if another consumer is already working on a job, we ignore it and find the next one.
                job = db.query(InvoiceJob).filter(
                    InvoiceJob.status.in_([JobStatus.NEW, JobStatus.FAILED]),
                    InvoiceJob.retry_count < self.max_retries
                ).with_for_update(skip_locked=True).first()

                if not job:
                    db.close()
                    time.sleep(10)
                    continue

                # Mark as PROCESSING immediately to "claim" the job.
                job.status = JobStatus.PROCESSING
                job.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"[JOB START] ID: {job.file_id} | User: {job.user_email}")

                try:
                    # Execute the 4-step processing pipeline.
                    self._run_pipeline(job)
                    job.status = JobStatus.PROCESSED
                    logger.info(f"[JOB SUCCESS] ID: {job.file_id}")
                except Exception as e:
                    # If any step fails, increment retry count and mark as FAILED.
                    job.status = JobStatus.FAILED
                    job.retry_count += 1
                    job.error_message = str(e)
                    logger.error(f"[JOB FAILURE] ID: {job.file_id} | Error: {str(e)}")
                
                job.updated_at = datetime.utcnow()
                db.commit()
            except Exception as e:
                logger.error(f"Critical error in consumer loop: {e}")
                db.rollback()
            finally:
                db.close()

    def _run_pipeline(self, job):
        """
        The multi-stage pipeline for invoice processing.
        """
        # Step 1: Normalization (Downloading)
        logger.info(f"[{job.file_id}] Step 1/4: Normalizing (Downloading)")
        file_content = self._download_file(job)
        
        # Step 2: Parsing (MinerU)
        # TODO: Replace with actual MinerU / magic-pdf logic.
        logger.info(f"[{job.file_id}] Step 2/4: Parsing with MinerU")
        parsed_text = self._parse_with_mineru(file_content, job.file_name)
        
        # Step 3: Extraction (AI)
        # This uses the factory-selected AI provider (Gemini, Claude, or GPT).
        logger.info(f"[{job.file_id}] Step 3/4: Extraction using {os.getenv('AI_PROVIDER', 'anthropic')}")
        extracted_json = self.ai_client.extract_invoice_data(parsed_text)
        
        # Step 4: Storing
        # TODO: Implement Google Sheets append logic.
        logger.info(f"[{job.file_id}] Step 4/4: Storing extracted data")
        job.extracted_data = extracted_json

    def _download_file(self, job):
        """Downloads the raw bytes of the file from Google Drive."""
        service = self._get_drive_service(job.user_email)
        request = service.files().get_media(fileId=job.file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    def _parse_with_mineru(self, content, filename):
        """
        Placeholder for MinerU/magic-pdf. 
        In the future, this will convert PDF to high-quality Markdown.
        """
        return f"Mock parsed text from {filename}. In a real run, this would be the Markdown content of the invoice."

if __name__ == "__main__":
    consumer = ConsumerService()
    consumer.process_jobs()
