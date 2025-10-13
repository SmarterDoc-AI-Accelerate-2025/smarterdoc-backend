"""
Telephony service for handling Twilio phone calls and WebSocket media streams.
Bridges Twilio ⇄ Vertex AI Live API for real-time voice conversations.
"""
import asyncio
import base64
import json
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.config import settings
from app.util.logging import logger
from app.util.audio_codec import twilio_to_vertex, vertex_to_twilio, validate_audio_chunk
from app.services.vertex_live_service import VertexLiveSession


class TwilioService:
    """
    Service for managing Twilio phone calls and media streams.
    """
    
    def __init__(self):
        """Initialize Twilio client."""
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.warning("Twilio credentials not configured. Telephony features will be disabled.")
            self.client = None
        else:
            self.client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            logger.info("Initialized Twilio client")
    
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return self.client is not None
    
    def initiate_call(
        self,
        to_number: str,
        twiml_url: str,
        from_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call using Twilio.
        
        Args:
            to_number: Phone number to call (E.164 format, e.g., +1234567890)
            twiml_url: URL that returns TwiML instructions
            from_number: Caller ID (defaults to configured Twilio number)
            
        Returns:
            Dictionary with call details (sid, status, etc.)
        """
        if not self.is_configured():
            raise RuntimeError("Twilio not configured")
        
        try:
            caller_number = from_number or settings.TWILIO_NUMBER
            if not caller_number:
                raise ValueError("No caller number configured or provided")
            
            call = self.client.calls.create(
                to=to_number,
                from_=caller_number,
                url=twiml_url
            )
            
            logger.info(f"Initiated Twilio call: {call.sid} to {to_number}")
            
            return {
                "sid": call.sid,
                "to": to_number,
                "from": caller_number,
                "status": call.status,
                "direction": call.direction,
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e.msg} (code: {e.code})")
            raise
        except Exception as e:
            logger.error(f"Error initiating call: {e}")
            raise
    
    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """
        Get the status of a call.
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            Dictionary with call status details
        """
        if not self.is_configured():
            raise RuntimeError("Twilio not configured")
        
        try:
            call = self.client.calls(call_sid).fetch()
            
            return {
                "sid": call.sid,
                "status": call.status,
                "duration": call.duration,
                "start_time": str(call.start_time) if call.start_time else None,
                "end_time": str(call.end_time) if call.end_time else None,
            }
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e.msg} (code: {e.code})")
            raise
        except Exception as e:
            logger.error(f"Error getting call status: {e}")
            raise
    
    def hangup_call(self, call_sid: str) -> bool:
        """
        Hang up an active call.
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            True if successful
        """
        if not self.is_configured():
            raise RuntimeError("Twilio not configured")
        
        try:
            call = self.client.calls(call_sid).update(status="completed")
            logger.info(f"Hung up call: {call_sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e.msg} (code: {e.code})")
            return False
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
            return False


class TwilioMediaStreamHandler:
    """
    Handles bidirectional audio streaming between Twilio and Vertex AI Live API.
    """
    
    def __init__(
        self,
        stream_sid: str,
        vertex_session: VertexLiveSession,
    ):
        """
        Initialize media stream handler.
        
        Args:
            stream_sid: Twilio stream SID
            vertex_session: Vertex Live API session
        """
        self.stream_sid = stream_sid
        self.vertex_session = vertex_session
        self.is_active = False
        self._receive_task = None
        
        logger.info(f"Initialized media stream handler: {stream_sid}")
    
    async def start(self):
        """Start the media stream handler."""
        if not self.vertex_session.is_connected:
            await self.vertex_session.connect()
        
        self.is_active = True
        
        # Start background task to receive from Vertex and prepare for Twilio
        # (actual sending to Twilio happens in the websocket message loop)
        logger.info(f"Started media stream handler: {self.stream_sid}")
    
    async def stop(self):
        """Stop the media stream handler."""
        self.is_active = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        await self.vertex_session.disconnect()
        logger.info(f"Stopped media stream handler: {self.stream_sid}")
    async def process_twilio_audio(self, payload_base64: str) -> Optional[bytes]:
        """
        Process audio from Twilio and send to Vertex, then get response.
        
        Args:
            payload_base64: Base64-encoded μ-law audio from Twilio
            
        Returns:
            μ-law audio to send back to Twilio, or None
        """
        try:
            # Decode from base64
            ulaw_8k = base64.b64decode(payload_base64)
            
            # Validate
            if not validate_audio_chunk(ulaw_8k, "ulaw"):
                return None
            
            # Convert Twilio format to Vertex format
            pcm_16k = twilio_to_vertex(ulaw_8k)
            
            # Send to Vertex Live API
            await self.vertex_session.send_audio(pcm_16k)
            
            # Try to receive response from Vertex (non-blocking)
            pcm_24k = await self.vertex_session.receive_audio(timeout=0.01)
            
            if pcm_24k and len(pcm_24k) > 0:
                # Convert Vertex format back to Twilio format
                ulaw_8k_response = vertex_to_twilio(pcm_24k)
                return ulaw_8k_response
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing Twilio audio: {e}")
            return None
    
    def format_twilio_media_message(self, audio_data: bytes) -> dict:
        """
        Format audio data as a Twilio media message.
        
        Args:
            audio_data: μ-law audio bytes
            
        Returns:
            Dictionary formatted as Twilio media message
        """
        return {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {
                "payload": base64.b64encode(audio_data).decode('utf-8')
            }
        }


# Global service instance
_twilio_service: Optional[TwilioService] = None


def get_twilio_service() -> TwilioService:
    """Get or create the Twilio service singleton."""
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service


# Legacy compatibility function
def initiate_call(to_number: str, twiml_url: str) -> tuple[bool, str]:
    """
    Legacy function for backward compatibility.
    
    Args:
        to_number: Phone number to call
        twiml_url: TwiML URL
        
    Returns:
        Tuple of (success, message)
    """
    try:
        service = get_twilio_service()
        if not service.is_configured():
            return False, "Twilio not configured"
        
        result = service.initiate_call(to_number, twiml_url)
        return True, f"Call initiated: {result['sid']}"
    except Exception as e:
        return False, f"Error: {str(e)}"
