"""
Google Cloud Speech-to-Text service for audio transcription.

Reference: https://cloud.google.com/speech-to-text/docs/transcribe-streaming-audio
"""
import logging
from typing import AsyncIterator, Optional, Generator
from google.cloud import speech
import pyaudio

from ..config import ChatConfig

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """Service for converting speech to text using Google Cloud Speech-to-Text."""
    
    def __init__(self):
        """Initialize the Speech-to-Text client."""
        self.config = ChatConfig
        self.client = self._create_client()
        logger.info(
            f"Initialized Speech-to-Text client - project: {self.config.PROJECT_ID}, "
            f"language: {self.config.SPEECH_LANGUAGE_CODE}"
        )
    
    def _create_client(self) -> speech.SpeechClient:
        """
        Create and return a Google Cloud Speech-to-Text client.
        
        Requires:
        - GOOGLE_CLOUD_PROJECT: Your Google Cloud project ID
        - Authentication via Application Default Credentials (ADC)
        
        Reference: https://cloud.google.com/speech-to-text/docs/transcribe-streaming-audio
        """
        try:
            client = speech.SpeechClient()
            logger.info("Created Speech-to-Text client successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to create Speech-to-Text client: {str(e)}")
            raise
    
    def _build_streaming_config(
        self,
        language_code: Optional[str] = None,
        sample_rate: Optional[int] = None,
        single_utterance: Optional[bool] = None,
        enable_automatic_punctuation: Optional[bool] = None,
    ) -> speech.StreamingRecognitionConfig:
        """
        Build streaming recognition configuration.
        
        Args:
            language_code: Language code (e.g., 'en-US', 'zh-CN')
            sample_rate: Audio sample rate in Hz
            single_utterance: If True, stop listening after single utterance
            enable_automatic_punctuation: Enable automatic punctuation
            
        Returns:
            StreamingRecognitionConfig object
        """
        # Build recognition config
        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate or self.config.SPEECH_SAMPLE_RATE,
            language_code=language_code or self.config.SPEECH_LANGUAGE_CODE,
            enable_automatic_punctuation=(
                enable_automatic_punctuation 
                if enable_automatic_punctuation is not None 
                else self.config.SPEECH_ENABLE_AUTOMATIC_PUNCTUATION
            ),
            model=self.config.SPEECH_MODEL,
        )
        
        # Build streaming config
        streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=True,  # Get interim results while speaking
            single_utterance=(
                single_utterance 
                if single_utterance is not None 
                else self.config.SPEECH_SINGLE_UTTERANCE
            ),
        )
        
        return streaming_config
    
    def transcribe_audio_stream(
        self,
        audio_generator: Generator[bytes, None, None],
        language_code: Optional[str] = None,
        sample_rate: Optional[int] = None,
        single_utterance: Optional[bool] = None,
        enable_automatic_punctuation: Optional[bool] = None,
    ) -> Generator[dict, None, None]:
        """
        Transcribe streaming audio in real-time.
        
        Args:
            audio_generator: Generator that yields audio chunks
            language_code: Language code for recognition
            sample_rate: Audio sample rate in Hz
            single_utterance: If True, stop after single utterance
            enable_automatic_punctuation: Enable automatic punctuation
            
        Yields:
            Dictionary containing transcription results:
            {
                'transcript': str,
                'is_final': bool,
                'confidence': float (only for final results),
                'stability': float (only for interim results)
            }
        """
        try:
            # Build streaming config
            streaming_config = self._build_streaming_config(
                language_code=language_code,
                sample_rate=sample_rate,
                single_utterance=single_utterance,
                enable_automatic_punctuation=enable_automatic_punctuation,
            )
            
            # Create audio stream requests
            def request_generator():
                """Generator that yields StreamingRecognizeRequest objects."""
                # First request must contain the config
                yield speech.StreamingRecognizeRequest(
                    streaming_config=streaming_config
                )
                
                # Subsequent requests contain audio data
                for audio_chunk in audio_generator:
                    yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
            
            # Perform streaming recognition
            responses = self.client.streaming_recognize(
                requests=request_generator()
            )
            
            # Process responses
            for response in responses:
                if not response.results:
                    continue
                
                # The results list is consecutive
                result = response.results[0]
                
                if not result.alternatives:
                    continue
                
                # Get the top alternative
                alternative = result.alternatives[0]
                
                result_dict = {
                    'transcript': alternative.transcript,
                    'is_final': result.is_final,
                }
                
                # Add confidence for final results
                if result.is_final:
                    result_dict['confidence'] = alternative.confidence
                else:
                    # Add stability for interim results
                    result_dict['stability'] = result.stability
                
                yield result_dict
                
        except Exception as e:
            logger.error(f"Error in streaming transcription: {str(e)}")
            raise
    
    def capture_and_transcribe_microphone(
        self,
        duration_seconds: Optional[int] = None,
        language_code: Optional[str] = None,
        single_utterance: Optional[bool] = None,
        chunk_size: int = 1024,
    ) -> Generator[dict, None, None]:
        """
        Capture audio from microphone and transcribe in real-time.
        
        Args:
            duration_seconds: Maximum duration to record (None for continuous)
            language_code: Language code for recognition
            single_utterance: If True, stop after single utterance
            chunk_size: Audio chunk size in bytes
            
        Yields:
            Dictionary containing transcription results
        """
        # Audio recording parameters
        sample_rate = self.config.SPEECH_SAMPLE_RATE
        audio_format = pyaudio.paInt16
        channels = 1
        
        # Initialize PyAudio
        audio = pyaudio.PyAudio()
        
        try:
            # Open audio stream from microphone
            stream = audio.open(
                format=audio_format,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size,
            )
            
            logger.info("Started microphone recording...")
            
            # Audio generator
            def audio_generator():
                """Generator that reads audio from microphone."""
                chunks_count = 0
                max_chunks = None
                
                if duration_seconds:
                    max_chunks = int(sample_rate / chunk_size * duration_seconds)
                
                while True:
                    if max_chunks and chunks_count >= max_chunks:
                        break
                    
                    try:
                        data = stream.read(chunk_size, exception_on_overflow=False)
                        yield data
                        chunks_count += 1
                    except Exception as e:
                        logger.error(f"Error reading audio: {str(e)}")
                        break
            
            # Transcribe the audio stream
            for result in self.transcribe_audio_stream(
                audio_generator=audio_generator(),
                language_code=language_code,
                sample_rate=sample_rate,
                single_utterance=single_utterance,
            ):
                yield result
                
                # Stop if single utterance and final result received
                if single_utterance and result['is_final']:
                    break
        
        finally:
            # Clean up
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            audio.terminate()
            logger.info("Stopped microphone recording")
    
    def transcribe_audio_file(
        self,
        audio_content: bytes,
        language_code: Optional[str] = None,
        sample_rate: Optional[int] = None,
        enable_automatic_punctuation: Optional[bool] = None,
    ) -> dict:
        """
        Transcribe audio from file content (for short audio files).
        
        Args:
            audio_content: Audio file content as bytes
            language_code: Language code for recognition
            sample_rate: Audio sample rate in Hz
            enable_automatic_punctuation: Enable automatic punctuation
            
        Returns:
            Dictionary containing transcription result
        """
        try:
            # Build recognition config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate or self.config.SPEECH_SAMPLE_RATE,
                language_code=language_code or self.config.SPEECH_LANGUAGE_CODE,
                enable_automatic_punctuation=(
                    enable_automatic_punctuation 
                    if enable_automatic_punctuation is not None 
                    else self.config.SPEECH_ENABLE_AUTOMATIC_PUNCTUATION
                ),
                model=self.config.SPEECH_MODEL,
            )
            
            audio = speech.RecognitionAudio(content=audio_content)
            
            # Perform recognition
            response = self.client.recognize(config=config, audio=audio)
            
            # Extract results
            if not response.results:
                return {
                    'transcript': '',
                    'confidence': 0.0,
                }
            
            result = response.results[0]
            alternative = result.alternatives[0]
            
            return {
                'transcript': alternative.transcript,
                'confidence': alternative.confidence,
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio file: {str(e)}")
            raise
    
    def check_health(self) -> dict:
        """Check service health."""
        return {
            'status': 'healthy',
            'service': 'Google Cloud Speech-to-Text',
            'language': self.config.SPEECH_LANGUAGE_CODE,
            'sample_rate': self.config.SPEECH_SAMPLE_RATE,
        }


# Global service instance
_speech_service: Optional[SpeechToTextService] = None


def get_speech_service() -> SpeechToTextService:
    """Get or create the speech service singleton."""
    global _speech_service
    if _speech_service is None:
        _speech_service = SpeechToTextService()
    return _speech_service

