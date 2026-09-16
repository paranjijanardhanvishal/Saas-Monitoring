import pytest
from unittest.mock import AsyncMock, patch
from app.privacy.schemas import PrivacyFindingModel
from scripts import offline_analysis as oa

@pytest.mark.asyncio
async def test_run_offline_analysis(mocker):
    # Mock environment variables
    mocker.patch('os.getenv', side_effect=lambda k, d=None: "mongodb://mock" if k == "MONGODB_URI" else "mock_db")
    
    # Mock MongoDB Client
    from unittest.mock import Mock, MagicMock
    mock_client_cls = mocker.patch('scripts.offline_analysis.AsyncIOMotorClient')
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_client_cls.return_value = mock_client
    
    # Mock finding files
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[{"file_id": "file_1", "name": "Confidential Report.docx"}])
    mock_db.files.find.return_value = mock_cursor
    mock_db.offline_baselines.update_one = AsyncMock()
    
    # Mock analyze_text
    mock_analyze = mocker.patch('scripts.offline_analysis.analyze_text')
    mock_analyze.return_value = PrivacyFindingModel(
        finding_id="mock_finding_1",
        event_id="offline_file_1",
        sensitivity_score=60.0,
        category="HIGH_RISK",
        factors=[]
    )
    
    # Mock vector insert
    mock_vdb = mocker.patch('scripts.offline_analysis.local_vdb')
    
    # Run the function
    await oa.run_offline_analysis()
    
    # Verify interactions
    mock_vdb.insert.assert_called_once_with("file_1", "Confidential Report.docx")
    mock_analyze.assert_called_once()
    mock_db.offline_baselines.update_one.assert_called_once()

