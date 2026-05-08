#!/usr/bin/env python3
"""
HTTP → Hermes Bridge
Enkel HTTP endpoint som tar emot meddelanden och forwardar till Hermes Agent
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import asyncio

app = FastAPI(title="Hermes HTTP Bridge")

# CORS - tillåt alla (eller begränsa till specifika IPs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Begränsa till säkra IPs
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Konfiguration från miljövariabler
HERMES_URL = os.getenv("HERMES_URL", "http://localhost:3000")
HERMES_TOKEN = os.getenv("HERMES_TOKEN", "")

def get_headers():
    """Hämta headers med auth token"""
    headers = {"Content-Type": "application/json"}
    if HERMES_TOKEN:
        headers["Authorization"] = f"Bearer {HERMES_TOKEN}"
    return headers

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "Hermes Bridge is running",
        "hermes_url": HERMES_URL,
        "version": "1.0"
    }

@app.post("/chat")
async def chat(message: dict):
    """
    Ta emot meddelande och skicka till Hermes
    
    Body: {"message": "Hej! Vad kan du göra?"}
    """
    msg_text = message.get("message", "").strip()
    if not msg_text:
        raise HTTPException(status_code=400, detail="message is required")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Skapa session
            session_resp = await client.post(
                f"{HERMES_URL}/api/sessions",
                json={"name": "Bridge Chat"},
                headers=get_headers()
            )
            
            if session_resp.status_code != 200:
                return {
                    "error": "Failed to create session",
                    "status": session_resp.status_code,
                    "details": session_resp.text
                }
            
            session = session_resp.json()
            session_id = session.get("id")
            
            # 2. Skicka meddelande
            msg_resp = await client.post(
                f"{HERMES_URL}/api/sessions/{session_id}/messages",
                json={"text": msg_text},
                headers=get_headers()
            )
            
            # 3. Vänta på svar (polla)
            # Hermes är asynkron, så vi pollar ett par gånger
            for _ in range(5):
                await asyncio.sleep(1)
                history_resp = await client.get(
                    f"{HERMES_URL}/api/sessions/{session_id}/messages",
                    headers=get_headers()
                )
                messages = history_resp.json()
                
                # Hitta senaste assistant-svar
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        return {
                            "session_id": session_id,
                            "response": msg.get("content"),
                            "status": "success"
                        }
            
            # Om vi inte fick svar
            return {
                "session_id": session_id,
                "response": "Agenten processar... (kolla dashboard)",
                "status": "processing"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def hermes_status():
    """Kolla Hermes status"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HERMES_URL}/api/status")
            return resp.json()
    except Exception as e:
        return {"error": str(e), "hermes_url": HERMES_URL}

if __name__ == "__main__":
    import uvicorn
    import asyncio  # Fix missing import
    uvicorn.run(app, host="0.0.0.0", port=8080)
