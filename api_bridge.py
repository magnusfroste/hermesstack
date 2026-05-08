#!/usr/bin/env python3
"""
API Bridge för AI-assistent
Enkel HTTP endpoint som proxyar till Hermes
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

app = FastAPI(title="Hermes AI Bridge")

# CORS för att tillåta requests från mig (eller annanstans)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Begränsa till min IP om du vill
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konfiguration
HERMES_URL = os.getenv("HERMES_URL", "http://localhost:3000")
HERMES_TOKEN = os.getenv("HERMES_TOKEN", "hermes-customer-secret-token-2024-magnusfroste")

@app.get("/")
async def root():
    return {"status": "Hermes AI Bridge is running", "target": HERMES_URL}

@app.post("/chat")
async def chat(request: Request):
    """
    Proxy för chat till Hermes
    
    Body: {"message": "Hej! Vad kan du göra?"}
    """
    body = await request.json()
    message = body.get("message", "")
    
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    
    try:
        async with httpx.AsyncClient() as client:
            # Först skapa session om det behövs
            session_response = await client.post(
                f"{HERMES_URL}/api/sessions",
                json={"name": "AI Bridge Chat"},
                headers={"Authorization": f"Bearer {HERMES_TOKEN}"},
                timeout=10.0
            )
            
            if session_response.status_code != 200:
                return {
                    "error": "Failed to create session",
                    "details": session_response.text
                }
            
            session = session_response.json()
            session_id = session.get("id")
            
            # Skicka meddelande
            msg_response = await client.post(
                f"{HERMES_URL}/api/sessions/{session_id}/messages",
                json={"text": message},
                headers={"Authorization": f"Bearer {HERMES_TOKEN}"},
                timeout=60.0
            )
            
            return {
                "session_id": session_id,
                "response": msg_response.json()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def status():
    """Kolla Hermes status"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HERMES_URL}/api/status")
            return response.json()
    except Exception as e:
        return {"error": str(e), "hermes_url": HERMES_URL}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
