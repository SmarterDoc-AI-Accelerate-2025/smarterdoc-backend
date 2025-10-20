from fastapi import APIRouter, HTTPException, Request
from typing import List
from ...models.schemas import (
    AppointmentRequest, 
    AppointmentResponse,
    AppointmentCallResult
)
from ...services.telephony import get_twilio_service
from ...config import settings
import logging
import httpx

router = APIRouter()
logger = logging.getLogger(__name__)


def get_public_url(request: Request) -> str:
    """
    Get the public URL for this server.
    Uses X-Forwarded-Host header if available (for ngrok/Cloud Run).
    For local development, uses localhost.
    """
    # Check for forwarded host (ngrok, Cloud Run, etc.)
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    
    if forwarded_host:
        # For ngrok, use the forwarded host with https
        if "ngrok" in forwarded_host or "ngrok-free" in forwarded_host:
            return f"https://{forwarded_host}"
        # For Cloud Run, always use https
        if ".run.app" in forwarded_host:
            return f"https://{forwarded_host}"
        return f"{forwarded_proto}://{forwarded_host}"
    
    # Fallback to request host
    host = request.headers.get("host", "localhost:8080")
    
    # For ngrok domains, always use https
    if "ngrok" in host or "ngrok-free" in host:
        return f"https://{host}"
    
    # For local development, use localhost
    if "localhost" in host or "127.0.0.1" in host:
        return f"http://localhost:8080"
    
    # For Cloud Run domains, always use https
    if ".run.app" in host:
        return f"https://{host}"
    
    # Default scheme detection
    scheme = "https" if "443" in host else "http"
    return f"{scheme}://{host}"


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(req: AppointmentRequest, request: Request):
    """
    Create appointments by calling doctors sequentially.
    For each doctor in the list, initiate a phone call to book an appointment.
    
    Args:
        req: Appointment request with patient info and list of doctors
        
    Returns:
        AppointmentResponse with call results for each doctor
    """
    logger.info(f"Creating appointment for {req.firstName} {req.lastName}")
    logger.info(f"Number of doctors to call: {len(req.doctors)}")
    
    call_results: List[AppointmentCallResult] = []
    successful_calls = 0
    
    # Get Twilio service
    twilio_service = get_twilio_service()
    
    if not twilio_service.is_configured():
        logger.warning("Twilio not configured - using mock mode")
        # Mock response when Twilio is not configured
        for doctor in req.doctors:
            call_results.append(AppointmentCallResult(
                doctor_name=doctor.name,
                doctor_specialty=doctor.specialty,
                call_status="success",
                call_sid=f"MOCK_CALL_{doctor.npi}",
                message=f"Mock call initiated to {doctor.name} for appointment on {req.appointmentTime}"
            ))
            successful_calls += 1
        
        return AppointmentResponse(
            status="success",
            message=f"Successfully initiated {successful_calls} mock calls (Twilio not configured)",
            call_results=call_results,
            total_doctors=len(req.doctors),
            successful_calls=successful_calls
        )
    
    # Real Twilio calls using /call API
    # Fixed phone number for all appointment calls
    to_number = "+12019325000"
    
    for doctor in req.doctors:
        try:
            # Construct system instruction with appointment details
            system_instruction = f"""You are SmarterDoc Agent, a virtual assistant that helps patients schedule appointments with doctors.

                You are calling Dr. {doctor.name}, who is a {doctor.specialty} specialist.

                Patient Information:
                - Name: {req.firstName} {req.lastName}
                - Phone: {req.phone}
                - Date of Birth: {req.birth}
                - Gender: {req.gender}
                - Preferred Appointment Time: {req.appointmentTime}
                - Reason for Visit: {req.comment or 'General consultation'}

                Your task:
                1. Greet the doctor politely and introduce yourself
                2. Explain that you're calling on behalf of the patient {req.firstName} {req.lastName}
                3. Request to schedule an appointment around the preferred time: {req.appointmentTime}
                4. Mention the reason for the visit: {req.comment or 'General consultation'}
                5. Confirm the appointment details with the doctor
                6. Thank the doctor for their time

                Maintain a warm, respectful, and professional tone throughout the conversation."""

            logger.info(f"Initiating call to {to_number} for {doctor.name}")
            logger.info(f"System instruction length: {len(system_instruction)} chars")
            
            # Get public URL for internal API call
            public_url = get_public_url(request)
            logger.info(f"Public URL: {public_url}")
            
            # Call the /call API instead of direct Twilio service
            call_api_url = f"{public_url}/api/v1/telephony/call"
            logger.info(f"Call API URL: {call_api_url}")
            
            call_payload = {
                "to": to_number,
                "voice": settings.VERTEX_LIVE_VOICE,
                "system_instruction": system_instruction
            }
            
            # Make HTTP request to /call API
            # Add ngrok headers to simulate external request
            headers = {
                "Content-Type": "application/json",
                "x-forwarded-host": "corrina-nonfederated-gabriele.ngrok-free.dev",
                "x-forwarded-proto": "https"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    call_api_url,
                    json=call_payload,
                    headers=headers,
                    timeout=30.0
                )
                
                logger.info(f"HTTP Response Status: {response.status_code}")
                logger.info(f"HTTP Response Headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    logger.error(f"HTTP Error {response.status_code}: {response.text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Call API returned {response.status_code}: {response.text}"
                    )
                
                result = response.json()
            
            # Extract call_sid from API response
            call_sid = result.get("call_sid")
            
            call_results.append(AppointmentCallResult(
                doctor_name=doctor.name,
                doctor_specialty=doctor.specialty,
                call_status="success",
                call_sid=call_sid,
                message=f"Call initiated successfully via /call API. Call SID: {call_sid}"
            ))
            successful_calls += 1
            logger.info(f"Successfully initiated call for {doctor.name} via /call API: {call_sid}")
            
        except Exception as e:
            logger.error(f"Failed to call {doctor.name}: {str(e)}")
            call_results.append(AppointmentCallResult(
                doctor_name=doctor.name,
                doctor_specialty=doctor.specialty,
                call_status="failed",
                call_sid=None,
                message=f"Failed to initiate call via /call API: {str(e)}"
            ))
    
    # Determine overall status
    if successful_calls == 0:
        status = "failed"
        message = "Failed to initiate any calls"
    elif successful_calls == len(req.doctors):
        status = "success"
        message = f"Successfully initiated all {successful_calls} calls"
    else:
        status = "partial"
        message = f"Initiated {successful_calls} out of {len(req.doctors)} calls"
    
    return AppointmentResponse(
        status=status,
        message=message,
        call_results=call_results,
        total_doctors=len(req.doctors),
        successful_calls=successful_calls
    )
