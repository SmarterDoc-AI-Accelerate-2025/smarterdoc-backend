"""
Vertex AI Live API service for real-time voice conversations.
Handles bidirectional audio streaming with Gemini Live models.
"""
import asyncio
from typing import AsyncIterator, Optional, Callable, List
from google import genai
from google.genai.types import (
    LiveConnectConfig, 
    SpeechConfig, 
    VoiceConfig, 
    PrebuiltVoiceConfig,
    GenerateContentConfig,
    Tool,
    LiveClientRealtimeInput,
    Blob,
    Content,
    Part,
)

from app.config import settings
from app.util.logging import logger


class VertexLiveSession:
    """
    Manages a single Vertex AI Live API session for real-time voice interaction.
    """
    
    def __init__(
        self,
        model: str = None,
        voice: str = None,
        system_instruction: str = None,
        tools: Optional[list] = None,
    ):
        """
        Initialize Vertex Live session configuration.
        
        Args:
            model: Model name (default from settings)
            voice: Voice name (default from settings)
            system_instruction: System instruction for the model
            tools: Optional list of tools for function calling
        """
        self.model = model or settings.VERTEX_LIVE_MODEL
        self.voice = voice or settings.VERTEX_LIVE_VOICE
        self.system_instruction = system_instruction or settings.VERTEX_LIVE_SYSTEM_INSTRUCTION
        self.tools = tools
        
        # Initialize Gen AI client with Vertex AI
        self.client = genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
        )
        
        self.session = None
        self._is_connected = False
        
        # Warn if model doesn't look like a Live API model
        try:
            if isinstance(self.model, str) and "live" not in self.model:
                logger.warning(
                    f"Configured Vertex Live model '{self.model}' may not be a Live API model. "
                    "Use a Live model like 'models/gemini-2.0-flash-live-preview-04-09'."
                )
        except Exception:
            pass
        logger.info(f"Initialized Vertex Live session config - Model: {self.model}, Voice: {self.voice}")
    
    def _build_config(self) -> LiveConnectConfig:
        """
        Build Live API connection configuration.
        
        Returns:
            LiveConnectConfig object
        """
        # Voice configuration
        voice_config = VoiceConfig(
            prebuilt_voice_config=PrebuiltVoiceConfig(
                voice_name=self.voice
            )
        )
        
        # Speech configuration
        speech_config = SpeechConfig(
            voice_config=voice_config
        )
        
        # Generation configuration (optional)
        generation_config = None
        if hasattr(settings, 'GENAI_TEMPERATURE'):
            generation_config = GenerateContentConfig(
                temperature=settings.GENAI_TEMPERATURE,
                top_p=settings.GENAI_TOP_P,
                top_k=settings.GENAI_TOP_K,
                max_output_tokens=settings.GENAI_MAX_OUTPUT_TOKENS,
            )
        
        # Build Live connect config
        config_params = {
            "response_modalities": ["AUDIO"],  # We want audio output
            "speech_config": speech_config,
        }
        
        # Add system instruction if provided
        if self.system_instruction:
            # System instruction needs to be a Content object, not a plain string
            config_params["system_instruction"] = Content(
                parts=[Part(text=self.system_instruction)],
                role="system"
            )
            logger.info(f"System instruction configured: {self.system_instruction[:100]}...")
        
        # Add generation config if available
        if generation_config:
            config_params["generation_config"] = generation_config
        
        # Add tools if provided
        if self.tools:
            config_params["tools"] = self.tools
        
        return LiveConnectConfig(**config_params)
    
    async def connect(self):
        """
        Establish connection to Vertex AI Live API.
        """
        try:
            config = self._build_config()
            
            # Connect to Live API (returns async context manager)
            context_manager = self.client.aio.live.connect(
                model=self.model,
                config=config
            )
            
            # Enter async context and get the actual session
            self.session = await context_manager.__aenter__()
            self._context_manager = context_manager  # Keep reference for cleanup
            self._is_connected = True
            
            logger.info(f"Connected to Vertex Live API - Model: {self.model}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Vertex Live API: {e}")
            raise
    
    async def disconnect(self):
        """
        Close connection to Vertex AI Live API.
        """
        try:
            if hasattr(self, '_context_manager') and self._is_connected:
                await self._context_manager.__aexit__(None, None, None)
                self._is_connected = False
                self.session = None
                logger.info("Disconnected from Vertex Live API")
        except Exception as e:
            logger.error(f"Error disconnecting from Vertex Live API: {e}")
    
    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm;rate=16000"):
        """
        Send audio input to the Live API.
        
        Args:
            audio_data: PCM16 audio data (16kHz)
            mime_type: MIME type of the audio
        """
        if not self._is_connected or not self.session:
            raise RuntimeError("Session not connected. Call connect() first.")
        
        try:
            # Send audio using the same method as text
            await self.session.send(
                input=LiveClientRealtimeInput(
                    media_chunks=[Blob(
                        data=audio_data,
                        mime_type=mime_type
                    )]
                )
            )
        except Exception as e:
            logger.error(f"Error sending audio to Vertex Live API: {e}")
            raise
    
    async def send_text(self, text: str):
        """
        Send text input to the Live API.
        
        Args:
            text: Text message to send
        """
        if not self._is_connected or not self.session:
            raise RuntimeError("Session not connected. Call connect() first.")
        
        try:
            # Send text message (for system messages or debugging)
            await self.session.send(input=text)
            logger.debug(f"Sent text: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending text to Vertex Live API: {e}")
            raise
    
    async def receive_audio(self, timeout: float = 0.01) -> Optional[bytes]:
        """
        Receive audio output from the Live API (non-blocking).
        
        Args:
            timeout: Timeout in seconds for receiving (default 10ms)
            
        Returns:
            PCM16 audio data (24kHz) or None if no data available
        """
        if not self._is_connected or not self.session:
            raise RuntimeError("Session not connected. Call connect() first.")
        
        try:
            # Try to receive a message with timeout
            message = await asyncio.wait_for(
                self.session.receive().__anext__(), 
                timeout=timeout
            )
            
            # Debug: Log the message structure
            logger.debug(f"Received message type: {type(message)}")
            logger.debug(f"Message attributes: {dir(message)}")
            
            # Extract audio from the response
            server_content = getattr(message, "server_content", None)
            if not server_content:
                logger.debug("No server_content in message")
                return None
            
            logger.debug(f"server_content type: {type(server_content)}")
            
            model_turn = getattr(server_content, "model_turn", None)
            if not model_turn:
                logger.debug("No model_turn in server_content")
                return None
            
            if not model_turn.parts:
                logger.debug("No parts in model_turn")
                return None
            
            logger.debug(f"Found {len(model_turn.parts)} parts in model_turn")
            
            # Collect all audio parts
            audio_chunks = []
            for i, part in enumerate(model_turn.parts):
                logger.debug(f"Part {i}: has inline_data={hasattr(part, 'inline_data')}")
                if hasattr(part, 'inline_data') and part.inline_data:
                    mime_type = part.inline_data.mime_type if hasattr(part.inline_data, 'mime_type') else 'unknown'
                    logger.debug(f"Part {i} mime_type: {mime_type}")
                    if mime_type.startswith("audio/pcm"):
                        data_len = len(part.inline_data.data) if hasattr(part.inline_data, 'data') else 0
                        logger.debug(f"Part {i} audio data length: {data_len}")
                        audio_chunks.append(part.inline_data.data)
                elif hasattr(part, 'text'):
                    logger.debug(f"Part {i} has text: {part.text[:100] if part.text else 'empty'}")
            
            if audio_chunks:
                # Combine all audio chunks
                combined_audio = b''.join(audio_chunks)
                logger.info(f"✓ Received audio: {len(combined_audio)} bytes")
                return combined_audio
            else:
                logger.debug("No audio chunks found in parts")
            
            return None
            
        except asyncio.TimeoutError:
            # No data available within timeout
            return None
        except Exception as e:
            logger.error(f"Error receiving audio from Vertex Live API: {e}", exc_info=True)
            return None
    
    async def stream_conversation(
        self,
        audio_input_stream: AsyncIterator[bytes],
        audio_output_callback: Callable[[bytes], None],
    ):
        """
        Stream bidirectional audio conversation.
        
        Args:
            audio_input_stream: Async iterator yielding input audio chunks (16kHz PCM16)
            audio_output_callback: Callback function to handle output audio (24kHz PCM16)
        """
        if not self._is_connected:
            await self.connect()
        
        try:
            # Create two concurrent tasks: send and receive
            async def send_task():
                """Send audio from input stream to Live API."""
                try:
                    async for audio_chunk in audio_input_stream:
                        if audio_chunk and len(audio_chunk) > 0:
                            await self.send_audio(audio_chunk)
                except Exception as e:
                    logger.error(f"Error in send task: {e}")
            
            async def receive_task():
                """Receive audio from Live API and call output callback."""
                try:
                    while self._is_connected:
                        audio_output = await self.receive_audio()
                        if audio_output:
                            await audio_output_callback(audio_output)
                        else:
                            # Small delay to avoid busy waiting
                            await asyncio.sleep(0.001)
                except Exception as e:
                    logger.error(f"Error in receive task: {e}")
            
            # Run both tasks concurrently
            await asyncio.gather(send_task(), receive_task())
            
        except Exception as e:
            logger.error(f"Error in stream conversation: {e}")
            raise
        finally:
            await self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if session is connected."""
        return self._is_connected


class VertexLiveService:
    """
    Service for managing Vertex AI Live API sessions.
    """
    
    def __init__(self):
        """Initialize the Vertex Live service."""
        self.active_sessions = {}
        logger.info("Initialized Vertex Live service")
    
    def create_session(
        self,
        session_id: str,
        model: str = None,
        voice: str = None,
        system_instruction: str = None,
        tools: Optional[list] = None,
    ) -> VertexLiveSession:
        """
        Create a new Live API session.
        
        Args:
            session_id: Unique identifier for the session
            model: Model name
            voice: Voice name
            system_instruction: System instruction
            tools: Optional tools
            
        Returns:
            VertexLiveSession instance
        """
        session = VertexLiveSession(
            model=model,
            voice=voice,
            system_instruction=system_instruction,
            tools=tools,
        )
        
        self.active_sessions[session_id] = session
        logger.info(f"Created Vertex Live session: {session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[VertexLiveSession]:
        """Get an existing session by ID."""
        return self.active_sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Close and remove a session."""
        session = self.active_sessions.get(session_id)
        if session:
            await session.disconnect()
            del self.active_sessions[session_id]
            logger.info(f"Closed Vertex Live session: {session_id}")
    
    async def close_all_sessions(self):
        """Close all active sessions."""
        for session_id in list(self.active_sessions.keys()):
            await self.close_session(session_id)
        logger.info("Closed all Vertex Live sessions")


# Global service instance
_vertex_live_service: Optional[VertexLiveService] = None


def get_vertex_live_service() -> VertexLiveService:
    """Get or create the Vertex Live service singleton."""
    global _vertex_live_service
    if _vertex_live_service is None:
        _vertex_live_service = VertexLiveService()
    return _vertex_live_service

