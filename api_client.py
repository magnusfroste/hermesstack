#!/usr/bin/env python3
"""
Hermes API Client för AI-assistent
Möjliggör programmatic kommunikation med Hermes Agent
"""

import asyncio
import json
import websockets
import httpx
import sys
from typing import Optional, Dict, Any

# Konfiguration - läses från miljövariabler eller defaults
HERMES_URL = "https://hermes.froste.eu"
HERMES_TOKEN = "hermes-customer-secret-token-2024-magnusfroste"

class HermesClient:
    """Client för att prata med Hermes via API"""
    
    def __init__(self, url: str = HERMES_URL, token: str = HERMES_TOKEN):
        self.url = url
        self.token = token
        self.session_id: Optional[str] = None
        
    async def create_session(self, name: str = "AI Chat") -> str:
        """Skapa en ny session"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/sessions",
                json={"name": name},
                headers={"Authorization": f"Bearer {self.token}"}
            )
            data = response.json()
            self.session_id = data.get("id")
            return self.session_id
    
    async def send_message(self, message: str) -> Dict[str, Any]:
        """Skicka meddelande via HTTP API"""
        if not self.session_id:
            await self.create_session()
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/sessions/{self.session_id}/messages",
                json={"text": message},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=60.0
            )
            return response.json()
    
    async def chat_websocket(self, message: str):
        """Skicka meddelande via WebSocket (realtid)"""
        if not self.session_id:
            await self.create_session()
        
        ws_url = f"wss://{self.url.replace('https://', '')}/api/ws?token={self.token}"
        
        async with websockets.connect(ws_url) as ws:
            # Skicka prompt
            request = {
                "jsonrpc": "2.0",
                "method": "prompt.submit",
                "params": {
                    "session_id": self.session_id,
                    "text": message
                },
                "id": 1
            }
            await ws.send(json.dumps(request))
            
            # Lyssna på svar
            responses = []
            async for message in ws:
                data = json.loads(message)
                responses.append(data)
                
                # Avsluta när vi får slutet på strömmen
                if data.get("method") == "message.complete":
                    break
                    
            return responses
    
    async def get_history(self) -> list:
        """Hämta meddelandehistorik"""
        if not self.session_id:
            return []
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/sessions/{self.session_id}/messages",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            return response.json()

# CLI för direkt användning
async def main():
    if len(sys.argv) < 2:
        print("Användning: python api_client.py 'Hej! Vad kan du göra?'")
        sys.exit(1)
    
    message = sys.argv[1]
    client = HermesClient()
    
    print(f"🤖 Skickar till Hermes: {message}")
    print("-" * 50)
    
    try:
        # Använd HTTP API
        response = await client.send_message(message)
        print(f"✅ Svar: {json.dumps(response, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"❌ Fel: {e}")

if __name__ == "__main__":
    asyncio.run(main())
