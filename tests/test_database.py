import pytest
from app.database.mongodb import MongoDB, connect_to_mongo, close_mongo_connection, get_database, db_client

@pytest.mark.asyncio
async def test_connect_to_mongo(mocker):
    mock_client = mocker.patch('app.database.mongodb.AsyncIOMotorClient')
    mocker.patch('app.database.mongodb.settings.MONGODB_URI', 'mongodb://test:27017')
    
    await connect_to_mongo()
    import certifi
    mock_client.assert_called_once_with(
        'mongodb://test:27017', 
        tlsCAFile=certifi.where(), 
        tlsAllowInvalidCertificates=True
    )
    assert db_client.client is not None
    assert get_database() is not None

@pytest.mark.asyncio
async def test_close_mongo_connection(mocker):
    mock_client_instance = mocker.MagicMock()
    db_client.client = mock_client_instance
    
    await close_mongo_connection()
    mock_client_instance.close.assert_called_once()
