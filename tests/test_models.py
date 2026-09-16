from app.models.user import UserModel
from app.models.file import FileModel
from app.models.event import EventModel, ActionEnum
from datetime import datetime

def test_user_model():
    user = UserModel(user_id="123", email="test@example.com")
    assert user.user_id == "123"
    assert user.email == "test@example.com"
    assert user.source == "google_drive"

def test_file_model():
    file = FileModel(file_id="f1", name="Doc", mime_type="text/plain")
    assert file.file_id == "f1"
    assert file.name == "Doc"
    assert file.mime_type == "text/plain"

def test_event_model():
    event = EventModel(event_id="e1", action=ActionEnum.ACCESS)
    assert event.event_id == "e1"
    assert event.action == "ACCESS"
