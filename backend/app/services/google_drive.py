import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'credentials', 'credentials.json')
TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'credentials', 'token.json')

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.creds = None
        self.service = None

    def authenticate(self):
        """Authenticates the user using local OAuth flow and returns the service."""
        try:
            if os.path.exists(TOKEN_PATH):
                self.creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not os.path.exists(CREDENTIALS_PATH):
                        logger.error(f"Credentials not found at {CREDENTIALS_PATH}")
                        return None
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                
                with open(TOKEN_PATH, 'w') as token:
                    token.write(self.creds.to_json())
            
            self.service = build('drive', 'v3', credentials=self.creds)
            return self.service
        except Exception as e:
            logger.error(f"Error authenticating to Google Drive: {e}")
            return None

    def get_current_user(self):
        """Retrieves the current authenticated user's information."""
        if not self.service:
            self.authenticate()
        if not self.service:
            return None
            
        try:
            about = self.service.about().get(fields="user").execute()
            return about.get('user', {})
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def list_files(self, page_size=10):
        """Lists files from Google Drive."""
        if not self.service:
            self.authenticate()
        if not self.service:
            return []
            
        try:
            results = self.service.files().list(
                pageSize=page_size, 
                fields="nextPageToken, files(id, name, mimeType, owners, createdTime, modifiedTime, webViewLink)"
            ).execute()
            items = results.get('files', [])
            return items
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []

drive_service = GoogleDriveService()
