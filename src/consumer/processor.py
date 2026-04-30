import os
import json
import logging
import io
import time
from datetime import datetime, timezone
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
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

import tempfile
import subprocess
import os

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
                # Use timezone-aware UTC datetime for Python 3.12+ compatibility
                job.updated_at = datetime.now(timezone.utc)
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
                
                # Update the timestamp using timezone-aware UTC datetime
                job.updated_at = datetime.now(timezone.utc)
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
        
        # Ensure MinerU gets a PDF (Headless conversion step)
        pdf_content = self._convert_to_pdf(file_content, job.file_name)
        
        # Step 2: Parsing (MinerU)
        # TODO: Replace with actual MinerU / magic-pdf logic.
        logger.info(f"[{job.file_id}] Step 2/4: Parsing with MinerU")
        parsed_text = self._parse_with_mineru(pdf_content, job.file_name)
        
        # Step 3: Extraction (AI)
        # This uses the factory-selected AI provider (Gemini, Claude, or GPT).
        logger.info(f"[{job.file_id}] Step 3/4: Extraction using {os.getenv('AI_PROVIDER', 'anthropic')}")
        extracted_json = self.ai_client.extract_invoice_data(parsed_text)
        
        # DEBUG: Print the raw AI response to terminal
        logger.info(f"DEBUG - Raw AI Extraction: {json.dumps(extracted_json, indent=2)}")
        
        # Step 4: Storing
        logger.info(f"[{job.file_id}] Step 4/4: Storing extracted data to Google Sheets")
        job.extracted_data = extracted_json
        
        if "error" not in extracted_json:
            self._append_to_sheets(job, extracted_json)

    def _get_or_create_spreadsheet(self, user_email: str):
        """Finds or creates an 'output' folder, then the Spreadsheet inside it."""
        with SessionLocal() as db:
            user = db.query(UserCredential).filter_by(email=user_email).first()
            creds = Credentials.from_authorized_user_info(user.token_data)
            parent_folder_id = user.drive_folder_id
            
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        # 1. Find or create 'output' folder
        query_folder = f"name='output' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed=false"
        folders = drive_service.files().list(q=query_folder, spaces='drive', fields='files(id)').execute().get('files', [])
        
        if folders:
            output_folder_id = folders[0]['id']
        else:
            logger.info(f"Creating 'output' subfolder for {user_email}")
            metadata = {'name': 'output', 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_folder_id]}
            output_folder_id = drive_service.files().create(body=metadata, fields='id').execute().get('id')
            
        # 2. Find or create Spreadsheet
        sheet_name = "AuditBot_Extracted_Invoices"
        query_sheet = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and '{output_folder_id}' in parents and trashed=false"
        sheets = drive_service.files().list(q=query_sheet, spaces='drive', fields='files(id)').execute().get('files', [])
        
        if sheets:
            return sheets[0]['id'], sheets_service
            
        logger.info(f"Creating new spreadsheet '{sheet_name}' inside 'output' folder")
        spreadsheet = sheets_service.spreadsheets().create(body={'properties': {'title': sheet_name}}, fields='spreadsheetId').execute()
        sheet_id = spreadsheet.get('spreadsheetId')
        
        # Move spreadsheet into 'output' folder (Sheets API creates it in root)
        file = drive_service.files().get(fileId=sheet_id, fields='parents').execute()
        prev_parents = ",".join(file.get('parents', []))
        drive_service.files().update(fileId=sheet_id, addParents=output_folder_id, removeParents=prev_parents, fields='id, parents').execute()
        
        # Write Headers
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range="Sheet1!A1:F1", valueInputOption="RAW",
            body={"values": [["File ID", "File Name", "Vendor", "Date", "Amount", "Tax"]]}
        ).execute()
        
        return sheet_id, sheets_service

    def _append_to_sheets(self, job, extracted_data: dict):
        sheet_id, sheets_service = self._get_or_create_spreadsheet(job.user_email)
        row = [job.file_id, job.file_name, extracted_data.get('Vendor', ''), extracted_data.get('Date', ''), extracted_data.get('Amount', 0.0), extracted_data.get('Tax', 0.0)]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="Sheet1!A:F", valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={"values": [row]}
        ).execute()
        logger.info(f"Appended {job.file_name} data to Spreadsheet in output folder")

    def _download_file(self, job):
        """Downloads the raw bytes of the file from Google Drive."""
        service = self._get_drive_service(job.user_email)
        
        # Check metadata to see if it's a Google Workspace file
        file_metadata = service.files().get(fileId=job.file_id, fields='mimeType').execute()
        mime_type = file_metadata.get('mimeType', '')
        
        if mime_type.startswith('application/vnd.google-apps.'):
            # If it's a folder or non-exportable, we shouldn't try to download/export it
            if mime_type == 'application/vnd.google-apps.folder':
                 raise Exception(f"File {job.file_id} is a Folder. Folders cannot be processed as invoices.")
            
            # Workspace files must be exported (cannot be downloaded directly)
            logger.info(f"File {job.file_id} is a Google Workspace document ({mime_type}). Exporting as PDF.")
            request = service.files().export_media(fileId=job.file_id, mimeType='application/pdf')
            # Ensure the filename ends with .pdf so LibreOffice conversion is bypassed
            if not job.file_name.lower().endswith('.pdf'):
                job.file_name += '.pdf'
        else:
            # Standard binary files can be downloaded directly
            request = service.files().get_media(fileId=job.file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    def _convert_to_pdf(self, raw_bytes: bytes, file_name: str) -> bytes:
        """
        Converts non-PDF documents to PDF using headless LibreOffice.
        If the file is already a PDF, it returns the bytes unmodified.
        """
        if file_name.lower().endswith('.pdf'):
            return raw_bytes
            
        logger.info(f"File {file_name} is not a PDF. Converting headlessly via LibreOffice...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, file_name)
            
            # Write original file to disk
            with open(input_path, 'wb') as f:
                f.write(raw_bytes)
                
            # Command to run LibreOffice in headless mode
            command = [
                "soffice", 
                "--headless", 
                "--convert-to", 
                "pdf", 
                input_path, 
                "--outdir", 
                temp_dir
            ]
            
            try:
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                logger.error(f"LibreOffice conversion failed: {e.stderr.decode('utf-8', errors='replace')}")
                raise Exception(f"Failed to convert {file_name} to PDF")
            
            # Read the newly generated PDF
            base_name = os.path.splitext(file_name)[0]
            output_path = os.path.join(temp_dir, f"{base_name}.pdf")
            
            with open(output_path, 'rb') as f:
                return f.read()

    def _parse_with_mineru(self, content: bytes, filename: str) -> str:
        """
        Parses the PDF content into Markdown using MinerU (magic-pdf).
        """
        from magic_pdf.data.dataset import PymuDocDataset
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
        from magic_pdf.config.enums import SupportedPdfParseMethod
        from magic_pdf.data.data_reader_writer.base import DataWriter

        logger.info(f"Extracting markdown from {filename} using MinerU...")
        
        try:
            class DummyWriter(DataWriter):
                def write(self, path: str, data: bytes) -> None:
                    pass

            image_writer = DummyWriter()
            ds = PymuDocDataset(content)
            
            if ds.classify() == SupportedPdfParseMethod.TXT:
                infer_result = ds.apply(doc_analyze, ocr=False)
                pipe_result = infer_result.pipe_txt_mode(image_writer)
            else:
                infer_result = ds.apply(doc_analyze, ocr=True)
                pipe_result = infer_result.pipe_ocr_mode(image_writer)
            
            # Extract markdown content, images are discarded to dummy writer
            md_content = pipe_result.get_markdown('dummy_img_dir')
            return str(md_content)
                
        except Exception as e:
            logger.error(f"MinerU parsing failed for {filename}: {str(e)}")
            raise Exception(f"MinerU PDF parsing error: {str(e)}")

if __name__ == "__main__":
    consumer = ConsumerService()
    consumer.process_jobs()
