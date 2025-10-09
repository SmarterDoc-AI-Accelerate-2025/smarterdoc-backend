"""
Unit tests for chat service.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from google import genai
from google.genai import types

from ai_chat.services.chat_service import GenAIChatService
from ai_chat.models.schemas import ChatMessage


class TestGenAIChatService:
    """Tests for GenAIChatService class."""
    
    @patch('ai_chat.services.chat_service.genai.Client')
    @patch.dict('os.environ', {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True',
        'GOOGLE_CLOUD_PROJECT': 'test-project',
        'GOOGLE_CLOUD_LOCATION': 'us-central1'
    })
    def test_init_creates_client(self, mock_client_class):
        """Test service initialization creates client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        service = GenAIChatService()
        
        assert service.client == mock_client
        mock_client_class.assert_called_once_with(
            vertexai=True,
            project='test-project',
            location='us-central1'
        )
    
    def test_build_contents_simple_message(self):
        """Test building contents from simple message."""
        with patch('ai_chat.services.chat_service.genai.Client'):
            service = GenAIChatService()
            
            contents = service._build_contents("Hello!")
            
            assert len(contents) == 1
            assert contents[0].role == 'user'
    
    def test_build_contents_with_history(self):
        """Test building contents with history."""
        with patch('ai_chat.services.chat_service.genai.Client'):
            service = GenAIChatService()
            
            history = [
                ChatMessage(role="user", content="First message"),
                ChatMessage(role="model", content="First response"),
            ]
            
            contents = service._build_contents("Second message", history)
            
            assert len(contents) == 3
            assert contents[0].role == "user"
            assert contents[1].role == "model"
            assert contents[2].role == "user"
    
    def test_build_generation_config_defaults(self):
        """Test building generation config with defaults."""
        with patch('ai_chat.services.chat_service.genai.Client'):
            service = GenAIChatService()
            
            config = service._build_generation_config()
            
            assert config.temperature == 0.7
            assert config.top_p == 0.95
            assert config.top_k == 40
            assert config.max_output_tokens == 8192
    
    def test_build_generation_config_custom(self):
        """Test building generation config with custom values."""
        with patch('ai_chat.services.chat_service.genai.Client'):
            service = GenAIChatService()
            
            config = service._build_generation_config(
                temperature=0.9,
                max_tokens=2048
            )
            
            assert config.temperature == 0.9
            assert config.max_output_tokens == 2048
    
    @pytest.mark.asyncio
    @patch('ai_chat.services.chat_service.genai.Client')
    async def test_generate_response_success(self, mock_client_class):
        """Test successful response generation."""
        # Setup mock
        mock_client = Mock()
        mock_aio = Mock()
        mock_models = Mock()
        
        # Create mock response
        mock_response = Mock()
        mock_response.text = "This is a test response"
        mock_response.usage_metadata = Mock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30
        )
        mock_response.candidates = [Mock(finish_reason="STOP")]
        
        # Setup async mock
        mock_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio
        mock_client_class.return_value = mock_client
        
        service = GenAIChatService()
        
        result = await service.generate_response("Test message")
        
        assert result['message'] == "This is a test response"
        assert result['model_used'] == 'gemini-2.5-flash'
        assert result['usage']['total_token_count'] == 30
        assert result['finish_reason'] == "STOP"
    
    @pytest.mark.asyncio
    @patch('ai_chat.services.chat_service.genai.Client')
    async def test_generate_response_with_params(self, mock_client_class):
        """Test response generation with custom parameters."""
        mock_client = Mock()
        mock_aio = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Response"
        mock_response.usage_metadata = None
        mock_response.candidates = []
        
        mock_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio
        mock_client_class.return_value = mock_client
        
        service = GenAIChatService()
        
        result = await service.generate_response(
            message="Test",
            model="gemini-2.5-pro",
            temperature=0.9,
            max_tokens=1024,
            system_instruction="Be helpful"
        )
        
        # Verify the call was made with correct parameters
        call_args = mock_models.generate_content.call_args
        assert call_args.kwargs['model'] == 'gemini-2.5-pro'
        assert call_args.kwargs['config'].temperature == 0.9
        assert call_args.kwargs['system_instruction'] == "Be helpful"
    
    @pytest.mark.asyncio
    @patch('ai_chat.services.chat_service.genai.Client')
    async def test_generate_response_stream_success(self, mock_client_class):
        """Test successful streaming response generation."""
        mock_client = Mock()
        mock_aio = Mock()
        mock_models = Mock()
        
        # Create mock chunks
        mock_chunk1 = Mock()
        mock_chunk1.text = "First "
        mock_chunk2 = Mock()
        mock_chunk2.text = "Second "
        mock_chunk3 = Mock()
        mock_chunk3.text = "Third"
        
        async def async_generator():
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                yield chunk
        
        mock_models.generate_content_stream = Mock(return_value=async_generator())
        mock_aio.models = mock_models
        mock_client.aio = mock_aio
        mock_client_class.return_value = mock_client
        
        service = GenAIChatService()
        
        chunks = []
        async for chunk in service.generate_response_stream("Test message"):
            chunks.append(chunk)
        
        assert chunks == ["First ", "Second ", "Third"]
    
    def test_check_health(self):
        """Test health check returns correct info."""
        with patch('ai_chat.services.chat_service.genai.Client'):
            service = GenAIChatService()
            
            health = service.check_health()
            
            assert health['status'] == 'healthy'
            assert health['service'] == 'Google Gen AI'
            assert 'model' in health


class TestGetChatService:
    """Tests for get_chat_service singleton."""
    
    @patch('ai_chat.services.chat_service.genai.Client')
    def test_singleton_pattern(self, mock_client_class):
        """Test that get_chat_service returns same instance."""
        from ai_chat.services.chat_service import get_chat_service, _chat_service
        
        # Reset singleton
        import ai_chat.services.chat_service as service_module
        service_module._chat_service = None
        
        service1 = get_chat_service()
        service2 = get_chat_service()
        
        assert service1 is service2

