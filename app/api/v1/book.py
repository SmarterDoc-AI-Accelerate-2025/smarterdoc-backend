from fastapi import APIRouter, HTTPException
from typing import List
import httpx
from ...models.schemas import (
    BookRequest, 
    BookResponse, 
    AppointmentRequest, 
    AppointmentResponse,
    AppointmentCallResult
)
from ...services.telephony import get_twilio_service
from ...config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# TODO: implement appointment assistant
@router.post("/book", response_model=BookResponse)
def book(req: BookRequest):
    """Legacy book endpoint (kept for backward compatibility)"""
    from ...services.telephony import initiate_call
    ok, msg = initiate_call(req)
    return BookResponse(status=("initiated" if ok else "failed"), message=msg)


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(req: AppointmentRequest):
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
                call_sid=f"MOCK_CALL_{doctor.id}",
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
    
    # Real Twilio calls
    # Fixed phone number for all appointment calls
    to_number = "+12019325000"
    
    # Base URL for internal API calls
    base_url = "http://localhost:8080"  # Internal call within the same service
    
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
            
            # Use telephony API's /call endpoint with system_instruction parameter
            async with httpx.AsyncClient(timeout=30.0) as client:
                call_payload = {
                    "to": to_number,
                    "system_instruction": system_instruction,
                    "voice": settings.VERTEX_LIVE_VOICE
                }
                
                response = await client.post(
                    f"{base_url}/api/v1/telephony/call",
                    json=call_payload
                )
                response.raise_for_status()
                result = response.json()
            
            # Extract call_sid from response
            call_sid = result.get("call_sid")
            
            call_results.append(AppointmentCallResult(
                doctor_name=doctor.name,
                doctor_specialty=doctor.specialty,
                call_status="success",
                call_sid=call_sid,
                message=f"Call initiated successfully. Call SID: {call_sid}"
            ))
            successful_calls += 1
            logger.info(f"Successfully initiated call for {doctor.name}: {call_sid}")
            
        except Exception as e:
            logger.error(f"Failed to call {doctor.name}: {str(e)}")
            call_results.append(AppointmentCallResult(
                doctor_name=doctor.name,
                doctor_specialty=doctor.specialty,
                call_status="failed",
                call_sid=None,
                message=f"Failed to initiate call: {str(e)}"
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
