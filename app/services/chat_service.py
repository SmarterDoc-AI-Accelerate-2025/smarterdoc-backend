"""
Google Gen AI client service for chat functionality.
"""
import logging
from typing import Optional, List, Dict, Any, AsyncIterator
from google import genai
from google.genai import types

from app.config import settings
from app.models.schemas import ChatMessage

logger = logging.getLogger(__name__)


class GenAIChatService:
    """Service for interacting with Google Gen AI."""
    
    def __init__(self):
        """Initialize the Google Gen AI client."""
        self.client = self._create_client()
        logger.info(
            f"Initialized GenAI client with Vertex AI - project: {settings.GCP_PROJECT_ID}, "
            f"location: {settings.GCP_REGION}"
        )
    
    def _create_client(self) -> genai.Client:
        """
        Create and return a Google Gen AI client using Vertex AI.
        
        Requires:
        - GCP_PROJECT_ID: Your Google Cloud project ID
        - GCP_REGION: The region (e.g., us-central1)
        - Authentication via Application Default Credentials (ADC)
        
        Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart
        """
        try:
            # Create Vertex AI client
            client = genai.Client(
                vertexai=True,
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_REGION
            )
            logger.info("Created Vertex AI client successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to create GenAI client: {str(e)}")
            raise
    
    def _build_contents(
        self, 
        message: str, 
        history: Optional[List[ChatMessage]] = None
    ) -> List[types.Content]:
        """
        Build contents list from message and history.
        
        Args:
            message: Current user message
            history: Previous conversation history
            
        Returns:
            List of Content objects
        """
        contents = []
        
        # Add history if provided
        if history:
            for msg in history:
                content = types.Content(
                    role=msg.role,
                    parts=[types.Part.from_text(text=msg.content)]
                )
                contents.append(content)
        
        # Add current message
        user_content = types.Content(
            role='user',
            parts=[types.Part.from_text(text=message)]
        )
        contents.append(user_content)
        
        return contents
    
    def _build_generation_config(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> types.GenerateContentConfig:
        """Build generation config."""
        return types.GenerateContentConfig(
            temperature=temperature or getattr(settings, 'GENAI_TEMPERATURE', 0.7),
            top_p=getattr(settings, 'GENAI_TOP_P', 0.95),
            top_k=getattr(settings, 'GENAI_TOP_K', 40),
            max_output_tokens=max_tokens or getattr(settings, 'GENAI_MAX_OUTPUT_TOKENS', 8192),
        )
    
    async def generate_response(
        self,
        message: str,
        history: Optional[List[ChatMessage]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response using Google Gen AI.
        
        Args:
            message: User message
            history: Previous conversation history
            model: Model to use (defaults to config)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            system_instruction: System instruction for the model
            
        Returns:
            Dictionary containing response and metadata
        """
        try:
            model_name = model or settings.GEMINI_MODEL
            
            # Build contents - include system instruction in the message if provided
            if system_instruction:
                # Prepend system instruction to the first user message
                if history:
                    # Add system instruction as first message
                    modified_history = [
                        ChatMessage(role="user", content=f"System: {system_instruction}\n\nUser: {history[0].content}")
                    ] + history[1:]
                    contents = self._build_contents(message, modified_history)
                else:
                    # Add system instruction to current message
                    enhanced_message = f"System: {system_instruction}\n\nUser: {message}"
                    contents = self._build_contents(enhanced_message, None)
            else:
                contents = self._build_contents(message, history)
            
            config = self._build_generation_config(temperature, max_tokens)
            
            # Generate content
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            
            # Extract response text
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # Extract usage metadata
            usage_metadata = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_metadata = {
                    'prompt_token_count': getattr(response.usage_metadata, 'prompt_token_count', None),
                    'candidates_token_count': getattr(response.usage_metadata, 'candidates_token_count', None),
                    'total_token_count': getattr(response.usage_metadata, 'total_token_count', None),
                }
            
            # Extract finish reason
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = getattr(response.candidates[0], 'finish_reason', None)
            
            return {
                'message': response_text,
                'model_used': model_name,
                'usage': usage_metadata,
                'finish_reason': finish_reason,
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise
    
    async def generate_response_stream(
        self,
        message: str,
        history: Optional[List[ChatMessage]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        system_instruction: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response using Google Gen AI.
        
        Args:
            message: User message
            history: Previous conversation history
            model: Model to use (defaults to config)
            temperature: Temperature for generation
            system_instruction: System instruction for the model
            
        Yields:
            Chunks of generated text
        """
        try:
            model_name = model or settings.GEMINI_MODEL
            
            # Build contents - include system instruction in the message if provided
            if system_instruction:
                # Prepend system instruction to the first user message
                if history:
                    # Add system instruction as first message
                    modified_history = [
                        ChatMessage(role="user", content=f"System: {system_instruction}\n\nUser: {history[0].content}")
                    ] + history[1:]
                    contents = self._build_contents(message, modified_history)
                else:
                    # Add system instruction to current message
                    enhanced_message = f"System: {system_instruction}\n\nUser: {message}"
                    contents = self._build_contents(enhanced_message, None)
            else:
                contents = self._build_contents(message, history)
            
            config = self._build_generation_config(temperature)
            
            # Generate content with streaming
            async for chunk in self.client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config
            ):
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            raise
    
    def check_health(self) -> Dict[str, str]:
        """Check service health."""
        return {
            'status': 'healthy',
            'service': 'Google Gen AI',
            'model': settings.GEMINI_MODEL,
        }


# Global service instance
_chat_service: Optional[GenAIChatService] = None


def get_chat_service() -> GenAIChatService:
    """Get or create the chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = GenAIChatService()
    return _chat_service

