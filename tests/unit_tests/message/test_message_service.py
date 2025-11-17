"""
Tests for message history service
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime, timedelta

from langbot.pkg.api.http.service.message import MessageHistoryService


class MockApplication:
    """Mock Application for testing"""
    
    def __init__(self):
        self.logger = self._create_mock_logger()
        self.persistence_mgr = self._create_mock_persistence_manager()
    
    def _create_mock_logger(self):
        logger = Mock()
        logger.debug = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        return logger
    
    def _create_mock_persistence_manager(self):
        persistence_mgr = AsyncMock()
        persistence_mgr.execute_async = AsyncMock()
        persistence_mgr.serialize_model = Mock(side_effect=lambda cls, obj: {
            'id': 1,
            'bot_uuid': 'test-bot',
            'launcher_type': 'person',
            'launcher_id': '123',
            'sender_id': '123',
            'message_role': 'user',
            'message_content': 'Hello',
            'message_chain': [{'type': 'Plain', 'text': 'Hello'}],
            'created_at': datetime.now().isoformat(),
        })
        return persistence_mgr


@pytest.fixture
def mock_app():
    """Create a mock application"""
    return MockApplication()


@pytest.fixture
def message_service(mock_app):
    """Create a message history service instance"""
    return MessageHistoryService(mock_app)


@pytest.mark.asyncio
async def test_save_message(message_service, mock_app):
    """Test saving a message"""
    # Setup mock result
    mock_result = Mock()
    mock_result.lastrowid = 1
    mock_app.persistence_mgr.execute_async.return_value = mock_result
    
    # Test saving message
    message_id = await message_service.save_message(
        bot_uuid='test-bot',
        pipeline_uuid='test-pipeline',
        launcher_type='person',
        launcher_id='123',
        sender_id='123',
        message_role='user',
        message_content='Hello',
        message_chain=[{'type': 'Plain', 'text': 'Hello'}],
        query_id=1,
    )
    
    assert message_id == 1
    assert mock_app.persistence_mgr.execute_async.called


@pytest.mark.asyncio
async def test_get_conversation_history(message_service, mock_app):
    """Test getting conversation history"""
    # Setup mock result
    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=[Mock()])
    mock_app.persistence_mgr.execute_async.return_value = mock_result
    
    # Test getting history
    messages = await message_service.get_conversation_history(
        bot_uuid='test-bot',
        launcher_type='person',
        launcher_id='123',
        limit=10,
    )
    
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert mock_app.persistence_mgr.execute_async.called


@pytest.mark.asyncio
async def test_get_inactive_conversations(message_service, mock_app):
    """Test getting inactive conversations"""
    # Setup mock result
    mock_result = Mock()
    mock_row = Mock()
    mock_row.bot_uuid = 'test-bot'
    mock_row.launcher_type = 'person'
    mock_row.launcher_id = '123'
    mock_row.last_message_time = datetime.now() - timedelta(hours=48)
    mock_result.fetchall = Mock(return_value=[mock_row])
    mock_app.persistence_mgr.execute_async.return_value = mock_result
    
    # Test getting inactive conversations
    conversations = await message_service.get_inactive_conversations(
        bot_uuid='test-bot',
        inactive_hours=24,
        limit=10,
    )
    
    assert isinstance(conversations, list)
    assert len(conversations) == 1
    assert conversations[0]['bot_uuid'] == 'test-bot'
    assert conversations[0]['launcher_type'] == 'person'
    assert conversations[0]['launcher_id'] == '123'
    assert mock_app.persistence_mgr.execute_async.called


@pytest.mark.asyncio
async def test_delete_conversation_history(message_service, mock_app):
    """Test deleting conversation history"""
    # Setup mock result
    mock_result = Mock()
    mock_result.rowcount = 5
    mock_app.persistence_mgr.execute_async.return_value = mock_result
    
    # Test deleting history
    count = await message_service.delete_conversation_history(
        bot_uuid='test-bot',
        launcher_type='person',
        launcher_id='123',
    )
    
    assert count == 5
    assert mock_app.persistence_mgr.execute_async.called


@pytest.mark.asyncio
async def test_get_conversation_history_with_filters(message_service, mock_app):
    """Test getting conversation history with various filters"""
    # Setup mock result
    mock_result = Mock()
    mock_result.fetchall = Mock(return_value=[])
    mock_app.persistence_mgr.execute_async.return_value = mock_result
    
    # Test with multiple filters
    messages = await message_service.get_conversation_history(
        bot_uuid='test-bot',
        launcher_type='group',
        launcher_id='456',
        sender_id='789',
        pipeline_uuid='test-pipeline',
        limit=50,
        offset=10,
        since=datetime.now() - timedelta(days=7),
    )
    
    assert isinstance(messages, list)
    assert mock_app.persistence_mgr.execute_async.called
