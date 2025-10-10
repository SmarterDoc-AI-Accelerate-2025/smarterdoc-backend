"""
API routes for Speech-to-Text functionality.
"""
import logging
import json
from fastapi import APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    SpeechStreamRequest,
    HealthCheckResponse
)
from app.services.speech_service import SpeechToTextService, get_speech_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/speech", tags=["Speech-to-Text"])


@router.post("/stream/microphone")
async def stream_microphone_transcription(
    request: SpeechStreamRequest,
    service: SpeechToTextService = Depends(get_speech_service)
):
    """
    Start streaming transcription from microphone.
    
    This endpoint captures audio from the server's microphone and streams
    transcription results in real-time. Each line in the response is a JSON
    object with the transcription result.
    
    Args:
        request: Speech stream configuration
        service: Injected speech service
        
    Returns:
        StreamingResponse with transcription results as JSON lines
        
    Raises:
        HTTPException: If streaming fails
    """
    try:
        def generate():
            """Generator function for streaming transcription."""
            try:
                for result in service.capture_and_transcribe_microphone(
                    duration_seconds=request.duration_seconds,
                    language_code=request.language_code,
                    single_utterance=request.single_utterance,
                ):
                    # Send result as JSON line
                    yield json.dumps(result) + "\n"
                    
            except Exception as e:
                logger.error(f"Microphone streaming error: {str(e)}")
                error_result = {
                    'error': str(e),
                    'transcript': '',
                    'is_final': True
                }
                yield json.dumps(error_result) + "\n"
        
        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",  # Newline-delimited JSON
        )
        
    except Exception as e:
        logger.error(f"Stream endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start streaming: {str(e)}"
        )


@router.websocket("/stream/websocket")
async def websocket_stream_transcription(
    websocket: WebSocket,
    language_code: str = "en-US",
    sample_rate: int = 16000,
):
    """
    WebSocket endpoint for real-time audio streaming from browser.
    
    This endpoint receives audio data from the browser's microphone via WebSocket
    and streams back transcription results in real-time.
    
    Protocol:
    - Client sends binary audio data (LINEAR16 PCM format)
    - Server sends JSON text messages with transcription results:
      {
        "transcript": "...",
        "is_final": true/false,
        "confidence": 0.95  // only for final results
      }
    - Client sends "close" text message to end the stream
    
    Args:
        websocket: WebSocket connection
        language_code: Language code (e.g., 'en-US', 'zh-CN')
        sample_rate: Audio sample rate in Hz (default: 16000)
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted - language: {language_code}, sample_rate: {sample_rate}")
    
    service = get_speech_service()
    audio_buffer = []
    is_running = True
    transcription_started = False
    
    try:
        import asyncio
        import queue
        import threading
        
        # Use a queue for thread-safe audio buffering
        audio_queue = queue.Queue()
        
        def audio_generator():
            """Generator that yields audio chunks from the queue."""
            while is_running or not audio_queue.empty():
                try:
                    # Get audio with timeout to allow checking is_running
                    audio_chunk = audio_queue.get(timeout=0.1)
                    yield audio_chunk
                except queue.Empty:
                    # Yield empty bytes to keep the stream alive
                    continue
        
        # Queue for sending results back to client
        result_queue = queue.Queue()
        
        async def transcribe_stream():
            """Transcribe audio stream and send results back."""
            def run_transcription():
                """Run transcription in a thread since it's synchronous."""
                try:
                    for result in service.transcribe_audio_stream(
                        audio_generator=audio_generator(),
                        language_code=language_code,
                        sample_rate=sample_rate,
                        single_utterance=False,
                    ):
                        # Put result in queue for async sending
                        result_queue.put(('result', result))
                except Exception as e:
                    logger.error(f"Transcription error: {str(e)}")
                    result_queue.put(('error', str(e)))
                finally:
                    result_queue.put(('done', None))
            
            # Run transcription in a separate thread
            transcription_thread = threading.Thread(target=run_transcription, daemon=True)
            transcription_thread.start()
            return transcription_thread
        
        # Don't start transcription yet - wait for first audio chunk
        transcription_thread = None
        
        logger.info("Starting WebSocket message loop...")
        message_count = 0
        
        # Main message loop - process incoming messages and send results
        while is_running:
            try:
                # Try to receive message with a small timeout to allow checking result queue
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=0.1)
                    message_count += 1
                    
                    # Log first message and every 100th message
                    if message_count == 1 or message_count % 100 == 0:
                        logger.info(f"📨 Processed {message_count} messages")
                    
                    # Check message type
                    msg_type = message.get('type')
                    
                    if msg_type == 'websocket.disconnect':
                        logger.info("Client disconnected")
                        is_running = False
                        break
                    
                    # Handle text messages
                    if 'text' in message:
                        text = message['text']
                        logger.info(f"Received text message: {text}")
                        if text == 'close':
                            logger.info("Client requested to close connection")
                            is_running = False
                            break
                    
                    # Handle binary messages
                    elif 'bytes' in message:
                        audio_data = message['bytes']
                        
                        # Start transcription after receiving first audio chunk
                        if not transcription_started and audio_data:
                            logger.info(f"✓ Starting transcription (first chunk: {len(audio_data)} bytes)...")
                            transcription_started = True
                            transcription_thread = await transcribe_stream()
                            logger.info("✓ Transcription started successfully")
                        
                        # Add audio to queue
                        audio_queue.put(audio_data)
                    
                except asyncio.TimeoutError:
                    # No message received, that's OK - check for results to send
                    pass
                
                # Check for transcription results to send back to client
                try:
                    msg_type, data = result_queue.get_nowait()
                    
                    if msg_type == 'result':
                        await websocket.send_json(data)
                        if data.get('is_final'):
                            transcript = data.get('transcript', '')
                            logger.info(f"✅ Transcribed: {transcript[:80]}{'...' if len(transcript) > 80 else ''}")
                    elif msg_type == 'error':
                        logger.error(f"Sending error to client: {data}")
                        await websocket.send_json({
                            'error': data,
                            'transcript': '',
                            'is_final': True
                        })
                        is_running = False
                    elif msg_type == 'done':
                        logger.info("Transcription done")
                        break
                        
                except queue.Empty:
                    # No results to send, that's OK
                    pass
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.001)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected by client")
                is_running = False
                break
            except Exception as e:
                logger.error(f"❌ Error in message loop: {str(e)}", exc_info=True)
                is_running = False
                break
        
        # Stop transcription
        is_running = False
        logger.info(f"WebSocket session ended - processed {message_count} messages total")
        
        # Wait for transcription thread to finish (if it was started)
        if transcription_thread:
            transcription_thread.join(timeout=5.0)
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        is_running = False
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        is_running = False
        try:
            await websocket.send_json({
                'error': str(e),
                'transcript': '',
                'is_final': True
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info("WebSocket connection closed")


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(service: SpeechToTextService = Depends(get_speech_service)):
    """
    Check the health status of the Speech-to-Text service.
    
    Args:
        service: Injected speech service
    
    Returns:
        HealthCheckResponse with service status
    """
    try:
        health = service.check_health()
        # Return in the format expected by HealthCheckResponse
        return HealthCheckResponse(
            status=health['status'],
            service=health['service'],
            model=health['language']  # Use language as model field
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )

