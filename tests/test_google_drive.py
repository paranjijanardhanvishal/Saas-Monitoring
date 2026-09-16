from app.services.google_drive import GoogleDriveService
import pytest
from unittest.mock import patch, MagicMock

def test_google_drive_service_init():
    service = GoogleDriveService()
    assert service.creds is None
    assert service.service is None

@patch('app.services.google_drive.os.path.exists')
def test_authenticate_no_credentials(mock_exists):
    # Test authentication failing when no credentials exist
    mock_exists.return_value = False
    service = GoogleDriveService()
    
    result = service.authenticate()
    assert result is None
    
@patch('app.services.google_drive.build')
def test_get_current_user_mocked(mock_build):
    service = GoogleDriveService()
    service.service = MagicMock()
    service.service.about().get().execute.return_value = {'user': {'emailAddress': 'test@example.com'}}
    
    user = service.get_current_user()
    assert user is not None
    assert user['emailAddress'] == 'test@example.com'

@patch('app.services.google_drive.build')
def test_list_files_mocked(mock_build):
    service = GoogleDriveService()
    service.service = MagicMock()
    service.service.files().list().execute.return_value = {'files': [{'id': '1', 'name': 'file1'}]}
    
    files = service.list_files()
    assert len(files) == 1
    assert files[0]['id'] == '1'
