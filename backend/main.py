from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import logging
import os
import httpx

from services import save_to_airtable, send_confirmation_email, check_availability

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retell AI Config
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")

app = FastAPI(title="QuensultingAI Retell Webhook Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_frontend():
    """
    Serves the index.html frontend file from the root directory.
    This allows the entire app (frontend + backend) to be hosted as a single service on Render.
    """
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(parent_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "index.html not found"}

# ─────────────────────────────────────────
# RETELL: Create Web Call Session
# Called by the frontend to get an access_token
# which is then passed to the Retell Web SDK
# ─────────────────────────────────────────
@app.post("/create-web-call")
async def create_web_call():
    """
    Creates a Retell web call session and returns the access_token.
    The frontend uses this token with the Retell Web SDK to start a live voice call.
    """
    if not RETELL_API_KEY:
        raise HTTPException(status_code=500, detail="RETELL_API_KEY is not configured in the .env file.")
    if not RETELL_AGENT_ID:
        raise HTTPException(status_code=500, detail="RETELL_AGENT_ID is not configured in the .env file.")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.retellai.com/v2/create-web-call",
                headers={
                    "Authorization": f"Bearer {RETELL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"agent_id": RETELL_AGENT_ID},
                timeout=15.0
            )
            if response.status_code != 201:
                logger.error(f"Retell API error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Retell API error: {response.text}")
            data = response.json()
            logger.info(f"Created web call session: {data.get('call_id')}")
            return {"access_token": data["access_token"], "call_id": data.get("call_id")}
    except httpx.RequestError as e:
        logger.error(f"Network error calling Retell API: {e}")
        raise HTTPException(status_code=503, detail="Failed to reach Retell API. Check your internet connection.")

class AppointmentRequest(BaseModel):
    name: str
    phone: str
    service: str
    date: str
    time: str
    email: Optional[str] = None

class EscalationRequest(BaseModel):
    caller_name: Optional[str] = None
    reason: str

@app.post("/webhook/book_appointment")
async def handle_book_appointment(request: AppointmentRequest):
    """
    Webhook endpoint to be called by Retell AI Flow when the user wants to book an appointment.
    """
    # 0. Check availability
    is_available = check_availability(request.date, request.time)
    if not is_available:
        return {
            "status": "error",
            "message": f"I'm sorry, but {request.date} at {request.time} is already booked. Could you please suggest another time?",
            "details": {"available": False}
        }
        
    # 1. Save to Airtable
    db_success = save_to_airtable(
        name=request.name,
        phone=request.phone,
        service=request.service,
        date=request.date,
        time=request.time,
        email=request.email
    )
    
    # 2. Send Email if provided
    email_success = False
    if request.email:
        email_success = send_confirmation_email(
            patient_email=request.email,
            name=request.name,
            service=request.service,
            date=request.date,
            time=request.time
        )
    
    # Return a response that Retell AI can speak back to the user
    message = f"Appointment confirmed for {request.name} on {request.date} at {request.time} for {request.service}."
    if not db_success:
        message = "I'm sorry, I was unable to save your appointment in our database at this moment. Please try again later."
        
    return {
        "status": "success" if db_success else "error",
        "message": message,
        "details": {
            "airtable_saved": db_success,
            "email_sent": email_success
        }
    }


@app.post("/webhook/escalate_call")
async def handle_escalation(request: EscalationRequest):
    """
    Webhook endpoint to handle call escalation.
    """
    logger.info(f"Call escalated. Reason: {request.reason}")
    # In a real scenario, this could trigger a Twilio SMS, Slack message, etc.
    return {
        "status": "success",
        "message": "A human agent has been notified and will take over shortly."
    }

# Fallback for generic Retell AI Custom Tool format if they use the native Tool Calling feature
@app.post("/webhook/retell_custom_tool")
async def retell_custom_tool(request: Request):
    """
    Handles Retell AI native tool calling webhook format.
    Expects payload: { "call_id": "...", "name": "...", "arguments": "{...}" }
    """
    try:
        payload = await request.json()
        logger.info(f"Received custom tool payload: {payload}")
        
        tool_name = payload.get("name")
        args_str = payload.get("arguments", "{}")
        import json
        args = json.loads(args_str)
        
        if tool_name == "book_appointment":
            # Check availability first
            is_available = check_availability(args.get("date"), args.get("time"))
            if not is_available:
                return {"result": f"Failed: The requested time ({args.get('date')} {args.get('time')}) is already booked. Please ask the user to pick a different time."}
                
            db_success = save_to_airtable(
                name=args.get("name"),
                phone=args.get("phone"),
                service=args.get("service"),
                date=args.get("date"),
                time=args.get("time"),
                email=args.get("email")
            )
            if args.get("email"):
                send_confirmation_email(
                    patient_email=args.get("email"),
                    name=args.get("name"),
                    service=args.get("service"),
                    date=args.get("date"),
                    time=args.get("time")
                )
            return {"result": "Appointment successfully booked."}
            
        elif tool_name == "escalate_call":
            return {"result": "Escalation registered. Please tell the user a human will call them back."}
            
        else:
            return {"result": f"Unknown tool: {tool_name}"}
            
    except Exception as e:
        logger.error(f"Error processing custom tool: {e}")
        return {"result": "An error occurred while processing the tool."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
