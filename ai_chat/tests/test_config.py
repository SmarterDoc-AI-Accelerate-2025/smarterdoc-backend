"""
Unit tests for configuration module.
"""
import os
import pytest
from unittest.mock import patch
from ai_chat.config import ChatConfig


class TestChatConfig:
    """Tests for ChatConfig class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        assert ChatConfig.DEFAULT_TEMPERATURE == 0.7
        assert ChatConfig.DEFAULT_TOP_P == 0.95
        assert ChatConfig.DEFAULT_TOP_K == 40
        assert ChatConfig.DEFAULT_MAX_OUTPUT_TOKENS == 8192
        assert ChatConfig.SAFETY_BLOCK_THRESHOLD == "BLOCK_MEDIUM_AND_ABOVE"
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True',
        'GOOGLE_CLOUD_PROJECT': 'test-project-123',
        'GOOGLE_CLOUD_LOCATION': 'us-central1'
    })
    def test_vertexai_config_from_env(self):
        """Test Vertex AI configuration from environment variables."""
        # Reload config to pick up env vars
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        assert config.ChatConfig.USE_VERTEXAI is True
        assert config.ChatConfig.PROJECT_ID == 'test-project-123'
        assert config.ChatConfig.LOCATION == 'us-central1'
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True',
        'GOOGLE_CLOUD_PROJECT': 'test-project',
        'GOOGLE_CLOUD_LOCATION': 'europe-west1',
        'GENAI_MODEL': 'gemini-2.5-pro'
    })
    def test_custom_model_config(self):
        """Test custom model configuration."""
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        assert config.ChatConfig.DEFAULT_MODEL == 'gemini-2.5-pro'
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True',
        'GOOGLE_CLOUD_PROJECT': 'test-project',
        'GOOGLE_CLOUD_LOCATION': 'us-east1',
        'GENAI_TEMPERATURE': '0.9',
        'GENAI_TOP_P': '0.8',
        'GENAI_TOP_K': '30',
        'GENAI_MAX_OUTPUT_TOKENS': '4096'
    })
    def test_custom_generation_params(self):
        """Test custom generation parameters."""
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        assert config.ChatConfig.DEFAULT_TEMPERATURE == 0.9
        assert config.ChatConfig.DEFAULT_TOP_P == 0.8
        assert config.ChatConfig.DEFAULT_TOP_K == 30
        assert config.ChatConfig.DEFAULT_MAX_OUTPUT_TOKENS == 4096
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True',
        'GOOGLE_CLOUD_PROJECT': 'test-project',
        'GOOGLE_CLOUD_LOCATION': 'us-central1'
    }, clear=True)
    def test_validate_success(self):
        """Test successful configuration validation."""
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        # Should not raise exception
        assert config.ChatConfig.validate(strict=False) is True
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True'
    }, clear=True)
    def test_validate_missing_project_id(self):
        """Test validation fails when PROJECT_ID is missing."""
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        with pytest.raises(ValueError) as exc_info:
            config.ChatConfig.validate(strict=True)
        
        assert 'GOOGLE_CLOUD_PROJECT' in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'False',
        'GOOGLE_CLOUD_PROJECT': 'test-project',
        'GOOGLE_CLOUD_LOCATION': 'us-central1'
    }, clear=True)
    def test_validate_vertexai_disabled(self):
        """Test validation warning when Vertex AI is disabled."""
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        with pytest.raises(ValueError) as exc_info:
            config.ChatConfig.validate(strict=True)
        
        assert 'GOOGLE_GENAI_USE_VERTEXAI' in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'GOOGLE_GENAI_USE_VERTEXAI': 'True',
        'GOOGLE_CLOUD_PROJECT': 'test-project-456',
        'GOOGLE_CLOUD_LOCATION': 'asia-northeast1'
    })
    def test_get_config_summary(self):
        """Test configuration summary generation."""
        from importlib import reload
        from ai_chat import config
        reload(config)
        
        summary = config.ChatConfig.get_config_summary()
        
        assert summary['use_vertexai'] is True
        assert summary['project_id'] == 'test-project-456'
        assert summary['location'] == 'asia-northeast1'
        assert 'model' in summary
        assert 'temperature' in summary
        assert 'max_tokens' in summary

