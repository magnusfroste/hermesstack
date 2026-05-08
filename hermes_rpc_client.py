#!/usr/bin/env python3
"""
Hermes JSON-RPC Client
Använder Hermes interna JSON-RPC gateway för chat
"""

import asyncio
import json
import websockets
import httpx
import sys
from typing import Optional, Dict, Any, List

class HermesRPCClient:
    """
    Klient för Hermes JSON-RPC gateway
    
    Hermes använder tui_gateway med JSON-RPC över WebSocket:
    - ws://host:PORT/api/ws?token=XXX
    
    Metoder:
    - prompt.submit - skicka meddelande
    - session.list - lista sessioner
    - session.create - skapa ny session
    """
    
    def __init__(self, host: str, port: int = 3000, token: str = ""):
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/api/ws"
        if token:
            self.ws_url += f"?token={token}"
        self.session_id: Optional[str] = None
        self.ws = None
        
    async def create_session(self, name: str = "AI Chat") -> str:
        """Skapa ny session via HTTP API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/sessions",
                json={"name": name}
            )
            data = response.json()
            self.session_id = data.get("id")
            print(f"✅ Session skapad: {self.session_id}")
            return self.session_id
    
    async def connect_websocket(self):
        """Anslut till WebSocket"""
        self.ws = await websockets.connect(self.ws_url)
        print(f"✅ WebSocket ansluten: {self.ws_url}")
        
    async def send_prompt(self, text: str) -> List[Dict]:
        """
        Skicka prompt via WebSocket JSON-RPC
        
        Hermes protocol:
        {
            "jsonrpc": "2.0",
            "method": "prompt.submit",
            "params": {
                "session_id": "...",
                "text": "..."
            },
            "id": 1
        }
        """
        if not self.session_id:
            await self.create_session()
            
        if not self.ws:
            await self.connect_websocket()
        
        request = {
            "jsonrpc": "2.0",
            "method": "prompt.submit",
            "params": {
                "session_id": self.session_id,
                "text": text
            },
            "id": 1
        }
        
        await self.ws.send(json.dumps(request))
        print(f"📤 Skickade: {text}")
        
        # Samla alla svar
        responses = []
        try:
            async for message in self.ws:
                data = json.loads(message)
                responses.append(data)
                
                # Logga viktiga events
                if data.get("method") == "message.start":
                    print("🤖 Agent börjar skriva...")
                elif data.get("method") == "message.delta":
                    # Printa texten direkt
                    content = data.get("params", {}).get("content", "")
                    if content:
                        print(content, end="", flush=True)
                elif data.get("method") == "message.complete":
                    print("\n✅ Meddelande klart")
                    break
                elif "error" in data:
                    print(f"❌ Fel: {data['error']}")
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Anslutning stängd")
            
        return responses
    
    async def chat(self, message: str) -> str:
        """Enkel chat-metod"""
        responses = await self.send_prompt(message)
        
        # Extrahera svaret
        full_response = ""
        for resp in responses:
            if resp.get("method") == "message.delta":
                full_response += resp.get("params", {}).get("content", "")
                
        return full_response
    
    async def close(self):
        """Stäng anslutningar"""
        if self.ws:
            await self.ws.close()
            print("🔌 WebSocket stängd")

# Enkel CLI
async def main():
    if len(sys.argv) < 2:
        print("Användning: python hermes_rpc_client.py 'Hej Hermes!'")
        print("\nExempel:")
        print('  python hermes_rpc_client.py "Vad kan du göra?"')
        sys.exit(1)
    
    message = sys.argv[1]
    
    # Konfiguration - ändra till din server
    host = "hermes.froste.eu"  # Eller din VPS IP
    port = 443  # HTTPS/WSS port
    token = "hermes-customer-secret-token-2024-magnusfroste"
    
    # Använd HTTPS/WSS för produktion
    client = HermesRPCClient(host, 443, token)
    client.base_url = f"https://{host}"
    client.ws_url = f"wss://{host}/api/ws?token={token}"
    
    print(f"🚀 Ansluter till Hermes på {host}...")
    print("-" * 50)
    
    try:
        response = await client.chat(message)
        print("-" * 50)
        print(f"📥 Fullständigt svar:\n{response}")
    except Exception as e:
        print(f"❌ Fel: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
