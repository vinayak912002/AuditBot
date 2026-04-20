import os
import time
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.common.db import SessionLocal
from src.database.models import InvoiceJob, JobStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DriveWatcher:
    def __init__(self, folder_id):
        self.folder_id = folder_id
        self.creds = self._load_creds()
        self.service = build('drive', 'v3', credentials=self.creds)

    def _load_creds(self):
        # Assumes credentials.json is in the root
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        if not os.path.exists(creds_path):
            logger.warning(f"Credentials file not found at {creds_path}. Watcher will fail.")
            return None
        return service_account.Credentials.from_service_account_file(
            creds_path, scopes=['https://www.googleapis.com/auth/drive.readonly']
        )

    def poll_for_new_files(self):
        if not self.service:
            logger.error("Drive service not initialized.")
            return

        logger.info(f"Polling folder {self.folder_id} for new files...")
        
        try:
            query = f"'{self.folder_id}' in parents and trashed = false"
            results = self.service.files().list(
                q=query, fields="files(id, name, createdTime)"
            ).execute()
            files = results.get('files', [])

            with SessionLocal() as db:
                for file in files:
                    file_id = file['id']
                    file_name = file['name']
                    
                    # Check if job already exists
                    exists = db.query(InvoiceJob).filter(InvoiceJob.file_id == file_id).first()
                    if not exists:
                        logger.info(f"New file detected: {file_name} ({file_id})")
                        new_job = InvoiceJob(
                            file_id=file_id,
                            file_name=file_name,
                            status=JobStatus.PENDING
                        )
                        db.add(new_job)
                db.commit()
        except Exception as e:
            logger.error(f"Error polling Drive: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    watcher = DriveWatcher(FOLDER_ID)
    
    while True:
        watcher.poll_for_new_files()
        interval = int(os.getenv("POLL_INTERVAL", 60))
        time.sleep(interval)
