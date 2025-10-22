"""
Telephony API endpoints for Twilio integration.
Handles phone calls, TwiML generation, and WebSocket media streams.
"""
import json
import asyncio
from typing import Dict, Any
import time
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.util.logging import logger
from app.services.telephony import (
    get_twilio_service,
    TwilioMediaStreamHandler,
)
from app.services.vertex_live_service import get_vertex_live_service


router = APIRouter()


# ============================================
# Request/Response Models
# ============================================

class CallRequest(BaseModel):
    """Request to initiate an outbound call."""
    to: str = Field(..., description="Phone number to call (E.164 format, e.g., +1234567890)")
    from_number: str | None = Field(None, description="Caller ID (optional, uses configured number)")
    twiml_url: str | None = Field(None, description="Custom TwiML URL (optional)")
    voice: str | None = Field(None, description="Vertex AI voice name (optional)")
    system_instruction: str | None = Field(None, description="Custom system instruction (optional)")


class CallResponse(BaseModel):
    """Response from call initiation."""
    success: bool
    call_sid: str | None = None
    message: str


class CallStatusResponse(BaseModel):
    """Call status information."""
    sid: str
    status: str
    duration: int | None = None
    start_time: str | None = None
    end_time: str | None = None


# ============================================
# Helper Functions
# ============================================

class InstructionStore:
    """In-memory instruction store with simple TTL eviction."""
    def __init__(self, ttl_seconds: int = 600):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def set(self, token: str, instruction: str):
        now = time.time()
        self._store[token] = {"instruction": instruction, "ts": now}
        self._prune()

    def get(self, token: str) -> str | None:
        data = self._store.get(token)
        if not data:
            return None
        if time.time() - data["ts"] > self._ttl:
            # expired
            try:
                del self._store[token]
            except KeyError:
                pass
            return None
        return data["instruction"]

    def _prune(self):
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v["ts"] > self._ttl]
        for k in expired:
            try:
                del self._store[k]
            except KeyError:
                pass


instruction_store = InstructionStore(ttl_seconds=600)

def get_public_url(request: Request) -> str:
    """
    Get the public URL for this server.
    Uses X-Forwarded-Host header if available (for ngrok/Cloud Run).
    """
    # Check for environment variable override (for ngrok development)
    ngrok_url = getattr(settings, 'NGROK_URL', None)
    if ngrok_url:
        logger.info(f"get_public_url - Using NGROK_URL from settings: {ngrok_url}")
        return ngrok_url
    
    # Check for forwarded host (ngrok, Cloud Run, etc.)
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    
    logger.info(f"get_public_url - forwarded_host: {forwarded_host}")
    logger.info(f"get_public_url - forwarded_proto: {forwarded_proto}")
    
    if forwarded_host:
        # For ngrok, use the forwarded host with https
        if "ngrok" in forwarded_host or "ngrok-free" in forwarded_host:
            result = f"https://{forwarded_host}"
            logger.info(f"get_public_url - Using ngrok URL: {result}")
            return result
        # For Cloud Run, always use https
        if ".run.app" in forwarded_host:
            result = f"https://{forwarded_host}"
            logger.info(f"get_public_url - Using Cloud Run URL: {result}")
            return result
        result = f"{forwarded_proto}://{forwarded_host}"
        logger.info(f"get_public_url - Using forwarded URL: {result}")
        return result
    
    # Fallback to request host
    host = request.headers.get("host", "localhost:8080")
    logger.info(f"get_public_url - host: {host}")
    
    # For ngrok domains, always use https
    if "ngrok" in host or "ngrok-free" in host:
        result = f"https://{host}"
        logger.info(f"get_public_url - Using ngrok host URL: {result}")
        return result
    
    # For local development, use localhost
    if "localhost" in host or "127.0.0.1" in host:
        result = f"http://localhost:8080"
        logger.info(f"get_public_url - Using localhost URL: {result}")
        return result
    
    # For Cloud Run domains, always use https
    if ".run.app" in host:
        result = f"https://{host}"
        logger.info(f"get_public_url - Using Cloud Run host URL: {result}")
        return result
    
    # Default scheme detection
    scheme = "https" if "443" in host else "http"
    result = f"{scheme}://{host}"
    logger.info(f"get_public_url - Using default URL: {result}")
    return result


def generate_twiml(websocket_url: str, parameters: Dict[str, str] | None = None) -> str:
    """
    Generate TwiML for connecting a call to a WebSocket stream.
    Optionally include <Parameter> elements that Twilio will echo in the
    Media Streams 'start' event under customParameters.

    IMPORTANT: TwiML is XML. Attribute values MUST be XML-escaped, especially
    ampersands in query strings.
    """
    def escape_attr(value: str) -> str:
        if value is None:
            return ""
        # Escape XML attribute special characters
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("\"", "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # Escape URL for XML attribute context
    safe_url = escape_attr(websocket_url)

    params_xml = ""
    if parameters:
        for name, value in parameters.items():
            if value is None:
                continue
            safe_name = escape_attr(name)
            safe_value = escape_attr(value)
            params_xml += f"\n            <Parameter name=\"{safe_name}\" value=\"{safe_value}\" />"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{safe_url}">{params_xml}
        </Stream>
    </Connect>
</Response>"""


# ============================================
# API Endpoints
# ============================================

@router.post("/call", response_model=CallResponse)
async def initiate_call(request: Request):
    """
    Initiate an outbound phone call.
    
    The call will be connected to a Vertex AI Live API session for voice interaction.
    """
    try:
        # Check if this is a Twilio webhook (form data) or API call (JSON)
        content_type = request.headers.get("content-type", "")
        
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            # This is a Twilio webhook, redirect to /twiml endpoint
            logger.info("Received Twilio webhook on /call, serving TwiML via /twiml")
            return await get_twiml(request)

        # This is a regular API call with JSON
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Expected JSON body for /call API requests")

        try:
            call_request = CallRequest(**body)
        except ValidationError as ve:
            raise HTTPException(status_code=422, detail=ve.errors())
        
        # Check if Twilio is configured
        twilio_service = get_twilio_service()
        if not twilio_service.is_configured():
            raise HTTPException(
                status_code=503,
                detail="Twilio service is not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
            )
        
        # Get public URL for TwiML callback
        public_url = get_public_url(request)
        logger.info(f"Telephony /call API - Public URL: {public_url}")
        logger.info(f"Telephony /call API - Request headers: {dict(request.headers)}")
        
        # Build TwiML URL (with optional voice, system instruction, and initial message as query params)
        twiml_url = call_request.twiml_url
        if not twiml_url:
            twiml_url = f"{public_url}/api/v1/telephony/twiml"
            # Add query parameters
            params = []
            from urllib.parse import quote
            if call_request.voice:
                params.append(f"voice={quote(call_request.voice)}")
            # For long instructions, avoid putting raw text in URL; store and pass token
            token: str | None = None
            if call_request.system_instruction:
                token = uuid4().hex
                instruction_store.set(token, call_request.system_instruction)
                params.append(f"token={quote(token)}")
            if params:
                twiml_url += "?" + "&".join(params)
            logger.info(f"Telephony /call API - Generated TwiML URL: {twiml_url}")
        
        # Initiate the call
        result = twilio_service.initiate_call(
            to_number=call_request.to,
            twiml_url=twiml_url,
            from_number=call_request.from_number,
        )
        
        logger.info(f"Call initiated successfully: {result['sid']}")
        
        return CallResponse(
            success=True,
            call_sid=result["sid"],
            message=f"Call initiated to {call_request.to}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_sid}", response_model=CallStatusResponse)
async def get_call_status(call_sid: str):
    """
    Get the status of a call.
    """
    try:
        twilio_service = get_twilio_service()
        if not twilio_service.is_configured():
            raise HTTPException(status_code=503, detail="Twilio not configured")
        
        status = twilio_service.get_call_status(call_sid)
        return CallStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting call status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/call/{call_sid}/hangup")
async def hangup_call(call_sid: str):
    """
    Hang up an active call.
    """
    try:
        twilio_service = get_twilio_service()
        if not twilio_service.is_configured():
            raise HTTPException(status_code=503, detail="Twilio not configured")
        
        success = twilio_service.hangup_call(call_sid)
        
        if success:
            return {"success": True, "message": f"Call {call_sid} hung up"}
        else:
            raise HTTPException(status_code=500, detail="Failed to hang up call")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error hanging up call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.api_route("/twiml", methods=["GET", "POST"])
async def get_twiml(
    request: Request, 
    voice: str | None = None, 
    instruction: str | None = None,
    token: str | None = None,
):
    """
    Generate TwiML for Twilio to connect the call to our WebSocket.
    
    Query parameters:
    - voice: Optional Vertex AI voice name
    - instruction: Optional system instruction (URL-encoded)
    """
    try:
        # Use the same get_public_url function for consistency
        public_url = get_public_url(request)
        
        # Determine WebSocket scheme based on public URL
        if public_url.startswith("https://"):
            ws_scheme = "wss"
            # Extract host from public URL
            host = public_url.replace("https://", "")
        else:
            ws_scheme = "ws"
            # Extract host from public URL
            host = public_url.replace("http://", "")
        
        # Build WebSocket URL
        ws_url = f"{ws_scheme}://{host}/api/v1/telephony/twilio-stream"
        
        # Add query parameters if provided
        params = []
        from urllib.parse import quote
        if voice:
            params.append(f"voice={quote(voice)}")
        if instruction:
            params.append(f"instruction={quote(instruction)}")
        if token:
            params.append(f"token={quote(token)}")
        
        if params:
            ws_url += "?" + "&".join(params)
        
        # Generate TwiML with safe custom parameters for observability
        custom_params = {}
        if voice:
            custom_params["voice"] = voice
        if token:
            custom_params["token"] = token
        twiml = generate_twiml(ws_url, custom_params)
        
        logger.info(f"Generated TwiML with WebSocket URL: {ws_url}")
        logger.info(f"TwiML API - Public URL: {public_url}")
        logger.info(f"TwiML API - WebSocket scheme: {ws_scheme}")
        
        # Return TwiML with correct Content-Type
        return Response(
            content=twiml,
            media_type="text/xml",
            headers={"Content-Type": "text/xml; charset=utf-8"}
        )
        
    except Exception as e:
        logger.error(f"Error generating TwiML: {e}")
        # Return a basic error TwiML with correct Content-Type
        error_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was an error connecting the call.</Say>
</Response>"""
        return Response(
            content=error_twiml,
            media_type="text/xml",
            headers={"Content-Type": "text/xml; charset=utf-8"}
        )


@router.websocket("/twilio-stream")
async def twilio_stream_websocket(
    websocket: WebSocket,
    voice: str | None = None,
    instruction: str | None = None,
    token: str | None = None,
):
    """
    WebSocket endpoint for Twilio Media Streams.
    Bridges audio between Twilio and Vertex AI Live API.
    
    Query parameters:
    - voice: Optional Vertex AI voice name
    - instruction: Optional system instruction
    """
    logger.info(f"🔌 WebSocket connection attempt - Voice: {voice}, Instruction: {str(instruction)[:80] if instruction else None}, Token: {token}")
    logger.info(f"🔌 WebSocket URL: {websocket.url}")
    logger.info(f"🔌 WebSocket headers: {dict(websocket.headers)}")
    logger.info(f"🔌 WebSocket client: {websocket.client}")
    
    try:
        await websocket.accept()
        logger.info("✓ WebSocket connection accepted from Twilio")
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {e}")
        return
    
    stream_sid = None
    call_sid = None
    media_handler = None
    vertex_session = None
    
    try:
        # Get Vertex Live service
        vertex_service = get_vertex_live_service()
        
        # Main message loop
        while True:
            try:
                # Receive message from Twilio
                message_text = await websocket.receive_text()
                message = json.loads(message_text)
                
                event = message.get("event")
                
                # Handle different event types
                if event == "start":
                    # Stream started
                    stream_sid = message["start"]["streamSid"]
                    call_sid = message["start"]["callSid"]
                    # Extract custom parameters (voice/token) if present
                    try:
                        custom_params = message["start"].get("customParameters") or {}
                        if not voice and custom_params.get("voice"):
                            voice = custom_params.get("voice")
                        if not token and custom_params.get("token"):
                            token = custom_params.get("token")
                    except Exception:
                        pass
                    
                    logger.info(f"📞 Stream started - StreamSID: {stream_sid}, CallSID: {call_sid}")
                    logger.info("🤖 Starting Vertex Live AI session...")
                    
                    # Create Vertex Live session
                    # Resolve system instruction preference: explicit param > token store > default
                    system_instruction_text = None
                    if instruction:
                        system_instruction_text = instruction
                    elif token:
                        system_instruction_text = instruction_store.get(token)
                        if system_instruction_text is None:
                            logger.warning(f"⚠️ Instruction token not found or expired: {token}")
                    if not system_instruction_text:
                        system_instruction_text = settings.VERTEX_LIVE_SYSTEM_INSTRUCTION
                    voice_name = voice or settings.VERTEX_LIVE_VOICE
                    
                    # Create Vertex Live session with system instruction
                    vertex_session = vertex_service.create_session(
                        session_id=stream_sid,
                        voice=voice_name,
                        system_instruction=system_instruction_text,
                    )
                    
                    # Create media stream handler
                    media_handler = TwilioMediaStreamHandler(
                        stream_sid=stream_sid,
                        vertex_session=vertex_session,
                    )
                    
                    # Start the handler (connects to Vertex Live) - this must complete before processing audio
                    logger.info("🔄 Connecting to Vertex AI...")
                    await media_handler.start()
                    
                    # Small delay to ensure everything is fully initialized
                    await asyncio.sleep(0.1)
                    
                    logger.info(f"✅ Session ready! System instruction: {system_instruction_text[:80]}...")
                    logger.info("🎙️ Ready to receive audio from user")
                    
                elif event == "media":
                    # Audio data from Twilio
                    if not media_handler or not media_handler.is_active:
                        # Handler not ready yet, skip this audio chunk silently
                        # (This is normal during startup)
                        continue
                    
                    payload = message["media"]["payload"]
                    logger.debug(f"Received media: {len(payload)} chars")
                    
                    # Process audio through Vertex Live API
                    response_audio = await media_handler.process_twilio_audio(payload)
                    
                    # Send response back to Twilio if available
                    if response_audio:
                        logger.debug(f"Sending back: {len(response_audio)} bytes")
                        response_message = media_handler.format_twilio_media_message(response_audio)
                        await websocket.send_text(json.dumps(response_message))
                    else:
                        logger.debug("No response audio from AI")
                
                elif event == "mark":
                    # Mark event (can be used for timing/synchronization)
                    logger.debug(f"Mark event received: {message.get('mark', {}).get('name')}")
                
                elif event == "stop":
                    # Stream stopped
                    logger.info(f"Stream stopped - StreamSID: {stream_sid}")
                    break
                
                else:
                    logger.warning(f"Unknown event type: {event}")
            
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from Twilio: {e}")
                continue
            
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Continue processing other messages
                continue
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by Twilio")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        # Cleanup
        if media_handler:
            try:
                await media_handler.stop()
            except Exception as e:
                logger.error(f"Error stopping media handler: {e}")
        
        if stream_sid:
            try:
                await vertex_service.close_session(stream_sid)
            except Exception as e:
                logger.error(f"Error closing Vertex session: {e}")
        
        logger.info(f"Cleaned up WebSocket connection - StreamSID: {stream_sid}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for telephony service.
    """
    twilio_service = get_twilio_service()
    
    return {
        "status": "healthy",
        "service": "Telephony",
        "twilio_configured": twilio_service.is_configured(),
        "vertex_model": settings.VERTEX_LIVE_MODEL,
        "vertex_voice": settings.VERTEX_LIVE_VOICE,
        "vertex_live_region": getattr(settings, 'VERTEX_LIVE_REGION', settings.GCP_REGION),
    }


@router.get("/test-websocket")
async def test_websocket_url(request: Request):
    """
    Test endpoint to verify WebSocket URL generation.
    """
    try:
        public_url = get_public_url(request)
        
        # Determine WebSocket scheme based on public URL
        if public_url.startswith("https://"):
            ws_scheme = "wss"
            host = public_url.replace("https://", "")
        else:
            ws_scheme = "ws"
            host = public_url.replace("http://", "")
        
        ws_url = f"{ws_scheme}://{host}/api/v1/telephony/twilio-stream"
        
        return {
            "status": "success",
            "public_url": public_url,
            "websocket_url": ws_url,
            "websocket_scheme": ws_scheme,
            "host": host
        }
        
    except Exception as e:
        logger.error(f"Error in test-websocket: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/test-twiml")
async def test_twiml(request: Request):
    """
    Test endpoint to verify TwiML generation.
    """
    try:
        # Get host from request
        forwarded_host = request.headers.get("x-forwarded-host")
        host = forwarded_host if forwarded_host else request.headers.get("host", "localhost:8080")
        
        # Determine WebSocket scheme
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        ws_scheme = "wss" if forwarded_proto == "https" or forwarded_host else "ws"
        
        # Build WebSocket URL
        ws_url = f"{ws_scheme}://{host}/api/v1/telephony/twilio-stream"
        
        # Generate TwiML
        twiml = generate_twiml(ws_url)
        
        return {
            "status": "success",
            "websocket_url": ws_url,
            "twiml": twiml,
            "headers": {
                "host": host,
                "forwarded_host": forwarded_host,
                "forwarded_proto": forwarded_proto
            }
        }
        
    except Exception as e:
        logger.error(f"Error in test-twiml: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

