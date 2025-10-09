"""
Unit tests for Pydantic schemas.
"""
import pytest
from pydantic import ValidationError
from ai_chat.models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    HealthCheckResponse
)


class TestChatMessage:
    """Tests for ChatMessage schema."""
    
    def test_valid_chat_message(self):
        """Test creating a valid chat message."""
        msg = ChatMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
    
    def test_chat_message_model_role(self):
        """Test chat message with model role."""
        msg = ChatMessage(role="model", content="Hi there!")
        assert msg.role == "model"
        assert msg.content == "Hi there!"


class TestChatRequest:
    """Tests for ChatRequest schema."""
    
    def test_minimal_request(self):
        """Test minimal valid chat request."""
        req = ChatRequest(message="What is AI?")
        assert req.message == "What is AI?"
        assert req.history is None
        assert req.model is None
        assert req.temperature is None
        assert req.max_tokens is None
        assert req.system_instruction is None
    
    def test_full_request(self):
        """Test chat request with all fields."""
        history = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="model", content="Hi!")
        ]
        req = ChatRequest(
            message="Tell me more",
            history=history,
            model="gemini-2.5-flash",
            temperature=0.8,
            max_tokens=2048,
            system_instruction="You are helpful"
        )
        assert req.message == "Tell me more"
        assert len(req.history) == 2
        assert req.model == "gemini-2.5-flash"
        assert req.temperature == 0.8
        assert req.max_tokens == 2048
        assert req.system_instruction == "You are helpful"
    
    def test_empty_message_fails(self):
        """Test that empty message fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")
        
        errors = exc_info.value.errors()
        assert any('message' in str(e) for e in errors)
    
    def test_missing_message_fails(self):
        """Test that missing message fails validation."""
        with pytest.raises(ValidationError):
            ChatRequest()
    
    def test_temperature_range(self):
        """Test temperature validation range."""
        # Valid temperatures
        ChatRequest(message="test", temperature=0.0)
        ChatRequest(message="test", temperature=1.0)
        ChatRequest(message="test", temperature=2.0)
        
        # Invalid temperatures
        with pytest.raises(ValidationError):
            ChatRequest(message="test", temperature=-0.1)
        
        with pytest.raises(ValidationError):
            ChatRequest(message="test", temperature=2.1)
    
    def test_max_tokens_positive(self):
        """Test max_tokens must be positive."""
        ChatRequest(message="test", max_tokens=1)
        ChatRequest(message="test", max_tokens=1000)
        
        with pytest.raises(ValidationError):
            ChatRequest(message="test", max_tokens=0)
        
        with pytest.raises(ValidationError):
            ChatRequest(message="test", max_tokens=-1)


class TestChatResponse:
    """Tests for ChatResponse schema."""
    
    def test_minimal_response(self):
        """Test minimal valid chat response."""
        resp = ChatResponse(
            message="Here is my answer",
            model_used="gemini-2.5-flash"
        )
        assert resp.message == "Here is my answer"
        assert resp.role == "model"
        assert resp.model_used == "gemini-2.5-flash"
        assert resp.usage is None
        assert resp.finish_reason is None
    
    def test_full_response(self):
        """Test chat response with all fields."""
        resp = ChatResponse(
            message="Detailed answer here",
            role="model",
            model_used="gemini-2.5-pro",
            usage={
                "prompt_token_count": 10,
                "candidates_token_count": 50,
                "total_token_count": 60
            },
            finish_reason="STOP"
        )
        assert resp.message == "Detailed answer here"
        assert resp.usage["total_token_count"] == 60
        assert resp.finish_reason == "STOP"


class TestChatStreamRequest:
    """Tests for ChatStreamRequest schema."""
    
    def test_stream_request(self):
        """Test streaming chat request."""
        req = ChatStreamRequest(
            message="Tell me a story",
            temperature=0.9
        )
        assert req.message == "Tell me a story"
        assert req.temperature == 0.9
        assert req.history is None
    
    def test_stream_request_with_history(self):
        """Test streaming request with history."""
        history = [ChatMessage(role="user", content="Hi")]
        req = ChatStreamRequest(
            message="Continue",
            history=history
        )
        assert len(req.history) == 1


class TestHealthCheckResponse:
    """Tests for HealthCheckResponse schema."""
    
    def test_health_check_response(self):
        """Test health check response."""
        resp = HealthCheckResponse(
            status="healthy",
            service="Google Gen AI",
            model="gemini-2.5-flash"
        )
        assert resp.status == "healthy"
        assert resp.service == "Google Gen AI"
        assert resp.model == "gemini-2.5-flash"

