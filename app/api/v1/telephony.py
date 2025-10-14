"""
Telephony API endpoints for Twilio integration.
Handles phone calls, TwiML generation, and WebSocket media streams.
"""
import json
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

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

def get_public_url(request: Request) -> str:
    """
    Get the public URL for this server.
    Uses X-Forwarded-Host header if available (for ngrok/Cloud Run).
    """
    # Check for forwarded host (ngrok, Cloud Run, etc.)
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"
    
    # Fallback to request host
    host = request.headers.get("host", "localhost:8080")
    scheme = "https" if "443" in host else "http"
    return f"{scheme}://{host}"


def generate_twiml(websocket_url: str) -> str:
    """
    Generate TwiML for connecting a call to a WebSocket stream.
    
    Args:
        websocket_url: WebSocket URL for media streaming
        
    Returns:
        TwiML XML string
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""


# ============================================
# API Endpoints
# ============================================

@router.post("/call", response_model=CallResponse)
async def initiate_call(request: Request, call_request: CallRequest):
    """
    Initiate an outbound phone call.
    
    The call will be connected to a Vertex AI Live API session for voice interaction.
    """
    try:
        # Check if Twilio is configured
        twilio_service = get_twilio_service()
        if not twilio_service.is_configured():
            raise HTTPException(
                status_code=503,
                detail="Twilio service is not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
            )
        
        # Get public URL for TwiML callback
        public_url = get_public_url(request)
        
        # Build TwiML URL (with optional voice, system instruction, and initial message as query params)
        twiml_url = call_request.twiml_url
        if not twiml_url:
            twiml_url = f"{public_url}/api/v1/telephony/twiml"
            
            # Add query parameters for customization
            params = []
            if call_request.voice:
                params.append(f"voice={call_request.voice}")
            if call_request.system_instruction:
                # URL encode the system instruction
                from urllib.parse import quote
                params.append(f"instruction={quote(call_request.system_instruction)}")
            
            if params:
                twiml_url += "?" + "&".join(params)
        
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


@router.api_route("/twiml", methods=["GET", "POST"], response_class=PlainTextResponse)
async def get_twiml(
    request: Request, 
    voice: str | None = None, 
    instruction: str | None = None
):
    """
    Generate TwiML for Twilio to connect the call to our WebSocket.
    
    Query parameters:
    - voice: Optional Vertex AI voice name
    - instruction: Optional system instruction (URL-encoded)
    """
    try:
        # Get host from request
        forwarded_host = request.headers.get("x-forwarded-host")
        host = forwarded_host if forwarded_host else request.headers.get("host", "localhost:8080")
        
        # Determine WebSocket scheme
        # ngrok uses https, so WebSocket should be wss
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        ws_scheme = "wss" if forwarded_proto == "https" or forwarded_host else "ws"
        
        # Build WebSocket URL
        ws_url = f"{ws_scheme}://{host}/api/v1/telephony/twilio-stream"
        
        # Add query parameters if provided
        params = []
        if voice:
            params.append(f"voice={voice}")
        if instruction:
            params.append(f"instruction={instruction}")
        
        if params:
            ws_url += "?" + "&".join(params)
        
        # Generate TwiML
        twiml = generate_twiml(ws_url)
        
        logger.info(f"Generated TwiML with WebSocket URL: {ws_url}")
        logger.info(f"Request headers - Host: {host}, Proto: {forwarded_proto}, Forwarded-Host: {forwarded_host}")
        
        return twiml
        
    except Exception as e:
        logger.error(f"Error generating TwiML: {e}")
        # Return a basic error TwiML
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was an error connecting the call.</Say>
</Response>"""


@router.websocket("/twilio-stream")
async def twilio_stream_websocket(
    websocket: WebSocket,
    voice: str | None = None,
    instruction: str | None = None
):
    """
    WebSocket endpoint for Twilio Media Streams.
    Bridges audio between Twilio and Vertex AI Live API.
    
    Query parameters:
    - voice: Optional Vertex AI voice name
    - instruction: Optional system instruction
    """
    logger.info(f"WebSocket connection attempt - Voice: {voice}, Instruction: {instruction}")
    await websocket.accept()
    logger.info("✓ WebSocket connection accepted from Twilio")
    
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
                    
                    logger.info(f"📞 Stream started - StreamSID: {stream_sid}, CallSID: {call_sid}")
                    logger.info("🤖 Starting Vertex Live AI session...")
                    
                    # Create Vertex Live session
                    system_instruction_text = instruction or settings.VERTEX_LIVE_SYSTEM_INSTRUCTION
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
    }

