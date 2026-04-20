import os
import time
import json
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from src.common.db import SessionLocal
from src.database.models import InvoiceJob, JobStatus, UserCredential
from dotenv import load_dotenv

load_dotenv()

# Allow Oauthlib to accept scope changes (Google often adds 'openid')
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Added userinfo.email scope to identify who is logging in
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/userinfo.email'
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MultiUserDriveWatcher:
    """
    Service responsible for monitoring Google Drive folders for multiple users.
    It handles OAuth2 registration and periodic polling of files.
    """
    def __init__(self):
        # Configuration for the Google OAuth2 client. 
        # These values must match your Google Cloud Console project.
        self.client_config = {
            "installed": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://localhost")]
            }
        }

    def _get_creds_from_dict(self, token_data):
        """
        Converts stored JSON/Dict back into Google Credentials objects.
        This allows us to reuse tokens saved in the database.
        """
        if isinstance(token_data, str):
            token_data = json.loads(token_data)
        return Credentials.from_authorized_user_info(token_data, SCOPES)

    def register_new_user(self):
        """
        Interactive CLI flow to authorize a new user.
        1. Opens a browser for Google Login.
        2. Receives the authorization code.
        3. Exchanges it for a token and stores it in the database.
        """
        flow = InstalledAppFlow.from_client_config(self.client_config, SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Identity Check: Use the 'oauth2' service to find out who just logged in.
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        email = user_info['email']

        with SessionLocal() as db:
            # Update existing user or create a new one
            existing = db.query(UserCredential).filter_by(email=email).first()
            token_json = json.loads(creds.to_json())
            
            if existing:
                existing.token_data = token_json
                logger.info(f"Updated credentials for: {email}")
            else:
                new_user = UserCredential(email=email, token_data=token_json)
                db.add(new_user)
                logger.info(f"Registered new user: {email}")
            db.commit()

    def poll_all_users(self):
        """
        The main loop logic for the Watcher.
        It fetches every user in the DB and checks their Drive one by one.
        """
        with SessionLocal() as db:
            users = db.query(UserCredential).all()
            if not users:
                logger.warning("No registered users found in database.")
                return

            for user in users:
                try:
                    self._poll_for_single_user(user)
                except Exception as e:
                    logger.error(f"Error polling Drive for {user.email}: {str(e)}")

    def _poll_for_single_user(self, user_record):
        """
        Checks a specific user's Drive folder for new files.
        """
        creds = self._get_creds_from_dict(user_record.token_data)
        
        # Automatic Token Refresh: If the access token is old, use the refresh token
        # to get a new one without bothering the user.
        if creds and creds.expired and creds.refresh_token:
            logger.info(f"Refreshing token for {user_record.email}")
            try:
                creds.refresh(Request())
                # Save the new token back to the database immediately.
                with SessionLocal() as db:
                    db_user = db.query(UserCredential).filter_by(email=user_record.email).first()
                    db_user.token_data = json.loads(creds.to_json())
                    db.commit()
            except Exception as refresh_error:
                logger.error(f"Could not refresh token for {user_record.email}: {refresh_error}")
                return

        # Build the Drive API client
        service = build('drive', 'v3', credentials=creds)
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID") 
        
        logger.info(f"Scanning Drive for user: {user_record.email}")
        # Search query: Look for non-trashed files inside the specific folder.
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        with SessionLocal() as db:
            for file in files:
                file_id = file['id']
                # Idempotency Check: Don't add the same file twice.
                # We use the unique 'file_id' from Google as our primary key reference.
                existing = db.query(InvoiceJob).filter_by(file_id=file_id).first()
                if not existing:
                    logger.info(f"User {user_record.email}: New file found -> {file['name']}")
                    db.add(InvoiceJob(
                        file_id=file_id,
                        file_name=file['name'],
                        user_email=user_record.email,
                        status=JobStatus.NEW
                    ))
            db.commit()

if __name__ == "__main__":
    watcher = MultiUserDriveWatcher()
    
    # If run with a flag, trigger registration flow
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--register":
        watcher.register_new_user()
    else:
        interval = int(os.getenv("POLL_INTERVAL", 60))
        while True:
            watcher.poll_all_users()
            time.sleep(interval)
