"""
Unit tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from ai_chat.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_chat_service():
    """Create mock chat service."""
    mock_service = Mock()
    return mock_service


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data['service'] == "AI Chat Service"
        assert data['version'] == "1.0.0"
        assert data['status'] == "running"
    
    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == "healthy"
        assert data['service'] == "AI Chat Service"


class TestChatEndpoint:
    """Tests for chat endpoint."""
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_chat_simple_message(self, mock_get_service, client):
        """Test simple chat message."""
        # Setup mock
        mock_service = Mock()
        mock_service.generate_response = AsyncMock(return_value={
            'message': 'Hello! How can I help you?',
            'model_used': 'gemini-2.5-flash',
            'usage': {'total_token_count': 50},
            'finish_reason': 'STOP'
        })
        mock_get_service.return_value = mock_service
        
        # Make request
        response = client.post(
            "/api/v1/chat/",
            json={"message": "Hello"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['message'] == 'Hello! How can I help you?'
        assert data['model_used'] == 'gemini-2.5-flash'
        assert data['role'] == 'model'
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_chat_with_history(self, mock_get_service, client):
        """Test chat with conversation history."""
        mock_service = Mock()
        mock_service.generate_response = AsyncMock(return_value={
            'message': 'Saturn',
            'model_used': 'gemini-2.5-flash',
            'usage': None,
            'finish_reason': 'STOP'
        })
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "What about the second largest?",
                "history": [
                    {"role": "user", "content": "What is the largest planet?"},
                    {"role": "model", "content": "Jupiter"}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['message'] == 'Saturn'
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_chat_with_parameters(self, mock_get_service, client):
        """Test chat with custom parameters."""
        mock_service = Mock()
        mock_service.generate_response = AsyncMock(return_value={
            'message': 'Creative response',
            'model_used': 'gemini-2.5-pro',
            'usage': None,
            'finish_reason': 'STOP'
        })
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "Write a poem",
                "model": "gemini-2.5-pro",
                "temperature": 0.9,
                "max_tokens": 2048,
                "system_instruction": "You are a poet"
            }
        )
        
        assert response.status_code == 200
        
        # Verify service was called with correct parameters
        call_args = mock_service.generate_response.call_args
        assert call_args.kwargs['temperature'] == 0.9
        assert call_args.kwargs['max_tokens'] == 2048
        assert call_args.kwargs['system_instruction'] == "You are a poet"
    
    def test_chat_missing_message(self, client):
        """Test chat fails without message."""
        response = client.post(
            "/api/v1/chat/",
            json={}
        )
        
        assert response.status_code == 422
    
    def test_chat_empty_message(self, client):
        """Test chat fails with empty message."""
        response = client.post(
            "/api/v1/chat/",
            json={"message": ""}
        )
        
        assert response.status_code == 422
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_chat_service_error(self, mock_get_service, client):
        """Test chat handles service errors."""
        mock_service = Mock()
        mock_service.generate_response = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/chat/",
            json={"message": "Test"}
        )
        
        assert response.status_code == 500
        assert "Failed to generate response" in response.json()['detail']


class TestChatStreamEndpoint:
    """Tests for chat stream endpoint."""
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_chat_stream_success(self, mock_get_service, client):
        """Test streaming chat."""
        async def mock_stream():
            yield "First "
            yield "Second "
            yield "Third"
        
        mock_service = Mock()
        mock_service.generate_response_stream = Mock(return_value=mock_stream())
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "Tell me a story"}
        )
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/plain; charset=utf-8'
        # Note: In real streaming, we'd need to read the response in chunks
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_chat_stream_with_parameters(self, mock_get_service, client):
        """Test streaming with parameters."""
        async def mock_stream():
            yield "Response"
        
        mock_service = Mock()
        mock_service.generate_response_stream = Mock(return_value=mock_stream())
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Test",
                "temperature": 0.8,
                "system_instruction": "Be concise"
            }
        )
        
        assert response.status_code == 200


class TestChatHealthCheck:
    """Tests for chat service health check."""
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_health_check_healthy(self, mock_get_service, client):
        """Test health check returns healthy status."""
        mock_service = Mock()
        mock_service.check_health = Mock(return_value={
            'status': 'healthy',
            'service': 'Google Gen AI',
            'model': 'gemini-2.5-flash'
        })
        mock_get_service.return_value = mock_service
        
        response = client.get("/api/v1/chat/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['service'] == 'Google Gen AI'
        assert data['model'] == 'gemini-2.5-flash'
    
    @patch('ai_chat.api.v1.chat.get_chat_service')
    def test_health_check_error(self, mock_get_service, client):
        """Test health check handles errors."""
        mock_service = Mock()
        mock_service.check_health = Mock(side_effect=Exception("Service error"))
        mock_get_service.return_value = mock_service
        
        response = client.get("/api/v1/chat/health")
        
        assert response.status_code == 503
        assert "unhealthy" in response.json()['detail'].lower()

