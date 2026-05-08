"""
AI Bridge Backend API
Exponerar endpoint för AI-assistent att kommunicera med Hermes
"""

from fastapi import APIRouter, HTTPException, Request
import httpx
import os

router = APIRouter(prefix="/ai-bridge", tags=["ai-bridge"])

HERMES_URL = os.getenv("HERMES_URL", "http://localhost:3000")
HERMES_TOKEN = os.getenv("HERMES_TOKEN", "")

@router.get("/")
async def status():
    """Health check"""
    return {
        "status": "AI Bridge active",
        "version": "1.0.0"
    }

@router.post("/chat")
async def chat(request: Request):
    """
    Ta emot meddelande från AI-assistent
    
    Body: {"message": "Hej!", "session_id": "optional"}
    """
    body = await request.json()
    message = body.get("message", "").strip()
    session_id = body.get("session_id")
    
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if HERMES_TOKEN:
                headers["Authorization"] = f"Bearer {HERMES_TOKEN}"
            
            # Skapa session om inte angiven
            if not session_id:
                session_resp = await client.post(
                    f"{HERMES_URL}/api/sessions",
                    json={"name": "AI Bridge Chat"},
                    headers=headers
                )
                session = session_resp.json()
                session_id = session.get("id")
            
            # Skicka meddelande
            msg_resp = await client.post(
                f"{HERMES_URL}/api/sessions/{session_id}/messages",
                json={"text": message},
                headers=headers
            )
            
            return {
                "success": True,
                "session_id": session_id,
                "hermes_response": msg_resp.json()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """Hämta meddelanden från en session"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if HERMES_TOKEN:
                headers["Authorization"] = f"Bearer {HERMES_TOKEN}"
            
            resp = await client.get(
                f"{HERMES_URL}/api/sessions/{session_id}/messages",
                headers=headers
            )
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
