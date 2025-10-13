"""
Audio codec utilities for converting between different audio formats.
Handles μ-law ↔ PCM16 conversion and sample rate conversion.

Required for Twilio ⇄ Vertex AI Live API audio bridging:
- Twilio: 8kHz μ-law (PCMU)
- Vertex Live: 16kHz PCM16 (input), 24kHz PCM16 (output)
"""
import io
import numpy as np
from scipy import signal
from app.util.logging import logger

# Handle audioop import (Python 3.13+ compatibility)
try:
    import audioop
except ModuleNotFoundError:
    # Python 3.13+ removed audioop, use audioop-lts instead
    try:
        import audioop_lts as audioop
    except ImportError:
        raise ImportError(
            "audioop module not found. For Python 3.13+, please install: pip install audioop-lts"
        )


def ulaw_to_pcm16(ulaw_data: bytes) -> bytes:
    """
    Convert μ-law encoded audio to PCM16 (linear).
    
    Args:
        ulaw_data: μ-law encoded audio bytes
        
    Returns:
        PCM16 encoded audio bytes
    """
    try:
        # audioop.ulaw2lin converts μ-law to linear PCM
        # The second parameter (2) specifies 16-bit samples (2 bytes per sample)
        pcm_data = audioop.ulaw2lin(ulaw_data, 2)
        return pcm_data
    except Exception as e:
        logger.error(f"Error converting μ-law to PCM16: {e}")
        raise


def pcm16_to_ulaw(pcm_data: bytes) -> bytes:
    """
    Convert PCM16 (linear) audio to μ-law encoding.
    
    Args:
        pcm_data: PCM16 encoded audio bytes
        
    Returns:
        μ-law encoded audio bytes
    """
    try:
        # audioop.lin2ulaw converts linear PCM to μ-law
        # The second parameter (2) specifies 16-bit samples
        ulaw_data = audioop.lin2ulaw(pcm_data, 2)
        return ulaw_data
    except Exception as e:
        logger.error(f"Error converting PCM16 to μ-law: {e}")
        raise


def resample_audio(audio_data: bytes, orig_rate: int, target_rate: int, 
                   sample_width: int = 2) -> bytes:
    """
    Resample audio from one sample rate to another using high-quality resampling.
    
    Args:
        audio_data: Input audio data as bytes (PCM16 format)
        orig_rate: Original sample rate in Hz
        target_rate: Target sample rate in Hz
        sample_width: Bytes per sample (2 for PCM16)
        
    Returns:
        Resampled audio data as bytes
    """
    if orig_rate == target_rate:
        return audio_data
    
    try:
        # Convert bytes to numpy array (int16 for PCM16)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate resampling ratio
        num_samples = int(len(audio_array) * target_rate / orig_rate)
        
        # Use scipy's high-quality resampling
        resampled_array = signal.resample(audio_array, num_samples)
        
        # Convert back to int16 and then to bytes
        resampled_bytes = resampled_array.astype(np.int16).tobytes()
        
        return resampled_bytes
    except Exception as e:
        logger.error(f"Error resampling audio from {orig_rate}Hz to {target_rate}Hz: {e}")
        raise


def twilio_to_vertex(ulaw_8k_data: bytes) -> bytes:
    """
    Convert Twilio audio format to Vertex AI Live API input format.
    Twilio: 8kHz μ-law → Vertex: 16kHz PCM16
    
    Args:
        ulaw_8k_data: Audio from Twilio (8kHz μ-law)
        
    Returns:
        Audio for Vertex AI Live API (16kHz PCM16)
    """
    try:
        # Step 1: Convert μ-law to PCM16
        pcm_8k = ulaw_to_pcm16(ulaw_8k_data)
        
        # Step 2: Resample from 8kHz to 16kHz
        pcm_16k = resample_audio(pcm_8k, orig_rate=8000, target_rate=16000)
        
        return pcm_16k
    except Exception as e:
        logger.error(f"Error converting Twilio audio to Vertex format: {e}")
        raise


def vertex_to_twilio(pcm_24k_data: bytes) -> bytes:
    """
    Convert Vertex AI Live API output format to Twilio audio format.
    Vertex: 24kHz PCM16 → Twilio: 8kHz μ-law
    
    Args:
        pcm_24k_data: Audio from Vertex AI Live API (24kHz PCM16)
        
    Returns:
        Audio for Twilio (8kHz μ-law)
    """
    try:
        # Step 1: Resample from 24kHz to 8kHz
        pcm_8k = resample_audio(pcm_24k_data, orig_rate=24000, target_rate=8000)
        
        # Step 2: Convert PCM16 to μ-law
        ulaw_8k = pcm16_to_ulaw(pcm_8k)
        
        return ulaw_8k
    except Exception as e:
        logger.error(f"Error converting Vertex audio to Twilio format: {e}")
        raise


def validate_audio_chunk(data: bytes, expected_format: str = "pcm16") -> bool:
    """
    Validate that audio chunk is not empty and has reasonable size.
    
    Args:
        data: Audio data bytes
        expected_format: Expected format ("pcm16" or "ulaw")
        
    Returns:
        True if valid, False otherwise
    """
    if not data or len(data) == 0:
        return False
    
    # Check minimum size (at least 160 bytes for 20ms @ 8kHz)
    if len(data) < 160:
        logger.warning(f"Audio chunk too small: {len(data)} bytes")
        return False
    
    # Check alignment for PCM16 (should be even number of bytes)
    if expected_format == "pcm16" and len(data) % 2 != 0:
        logger.warning(f"PCM16 audio not aligned: {len(data)} bytes")
        return False
    
    return True


# Audio configuration constants
class AudioConfig:
    """Audio format configuration constants."""
    
    # Twilio format
    TWILIO_SAMPLE_RATE = 8000
    TWILIO_ENCODING = "ulaw"
    
    # Vertex AI Live API format
    VERTEX_INPUT_SAMPLE_RATE = 16000
    VERTEX_OUTPUT_SAMPLE_RATE = 24000
    VERTEX_ENCODING = "pcm16"
    
    # Common settings
    SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
    CHANNELS = 1  # Mono
    
    # Chunk sizes (in samples)
    TWILIO_CHUNK_MS = 20  # 20ms chunks from Twilio
    TWILIO_CHUNK_SAMPLES = (TWILIO_SAMPLE_RATE * TWILIO_CHUNK_MS) // 1000  # 160 samples

