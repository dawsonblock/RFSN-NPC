from __future__ import annotations
import os
import time
from typing import Dict, Optional, List, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from dataclasses import dataclass

from .engine import ENGINE, RFSNHybridEngine
from .types import RFSNState
from .storage import ConversationMemory, FactsStore
from .version import __version__

class ChatRequest(BaseModel):
    message: str
    player_name: str = "Player"

class ChatResponse(BaseModel):
    response: str
    npc_name: str
    affinity: float
    mood: str
    attitude: str
    latency_ms: float
    event_type: str
    facts_used: List[str]

class NPCCreateRequest(BaseModel):
    preset: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    initial_affinity: Optional[float] = None
    initial_mood: Optional[str] = None

@dataclass
class NPCSession:
    npc_id: str
    state: RFSNState
    memory: ConversationMemory
    facts: FactsStore
    data_dir: str

    def save(self):
        self.state.save(os.path.join(self.data_dir, f"{self.npc_id}_state.json"))
        # Memory and facts save themselves on add, but we can ensure path existence
        pass

class RFSNAPIServer:
    def __init__(self, engine: RFSNHybridEngine = ENGINE, data_dir: str = "data"):
        self.app = FastAPI(title="RFSN Hybrid Engine API", version=__version__)
        self.engine = engine
        self.data_dir = data_dir
        self.sessions: Dict[str, NPCSession] = {}
        
        # Ensure data dir
        os.makedirs(self.data_dir, exist_ok=True)

        @self.app.get("/")
        async def root():
            """API health check."""
            return {
                "status": "ok",
                "engine": "RFSN Hybrid Engine",
                "version": __version__,
                "llm_loaded": self.engine is not None,
            }

        @self.app.get("/health")
        def health():
            """Simple health check."""
            return {"ok": True}

        @self.app.post("/npc/{npc_id}/chat", response_model=ChatResponse)
        async def chat_with_npc(npc_id: str, request: ChatRequest):
            """Send a message to an NPC and get a response."""
            # Use unified engine pipeline
            result = ENGINE.handle_message(
                npc_id=npc_id,
                text=request.message,
                user_name=request.player_name
            )
            
            return ChatResponse(
                response=result["text"],
                npc_name=result["state"]["npc_name"],
                affinity=result["state"]["affinity"],
                mood=result["state"]["mood"],
                attitude="Neutral", # TODO: Compute attitude from affinity if needed or add to snapshot
                latency_ms=0.0, # TODO: Track in engine
                event_type="chat",
                facts_used=result["facts_used"],
            )
        
        @self.app.post("/npc/{npc_id}/reset")
        async def reset_npc(npc_id: str, request: NPCCreateRequest = None):
            """Reset or create an NPC with specified settings."""
            # Remove old session
            if npc_id in self.sessions:
                del self.sessions[npc_id]
            
            # Clear files
            for suffix in ["_state.json", "_conversation.json", "_facts.json"]:
                path = os.path.join(self.data_dir, f"{npc_id}{suffix}")
                if os.path.exists(path):
                    os.remove(path)
            
            # Create new session
            if request and request.preset:
                # Use preset
                session = self._get_or_create_session(request.preset)
            else:
                # Use provided settings
                state = RFSNState(
                    npc_name=request.name if request else "NPC",
                    role=request.role if request else "Character",
                    affinity=request.initial_affinity if request else 0.5,
                    mood=request.initial_mood if request else "Neutral",
                    player_name="Player",
                    player_playstyle="Adventurer",
                )
                
                session = NPCSession(
                    npc_id=npc_id,
                    state=state,
                    memory=ConversationMemory(
                        os.path.join(self.data_dir, f"{npc_id}_conversation.json")
                    ),
                    facts=FactsStore(
                        os.path.join(self.data_dir, f"{npc_id}_facts.json")
                    ),
                    data_dir=self.data_dir,
                )
                self.sessions[npc_id] = session
            
            session.save()
            
            return {
                "status": "reset",
                "npc_id": npc_id,
                "name": session.state.npc_name,
            }
        
        @self.app.get("/npc/{npc_id}/history")
        async def get_conversation_history(
            npc_id: str, 
            limit: int = Query(20, ge=1, le=100)
        ):
            """Get conversation history for an NPC."""
            session = self._get_or_create_session(npc_id)
            turns = session.memory.last_n(limit)
            
            return {
                "npc_id": npc_id,
                "total_turns": len(session.memory.turns),
                "turns": [
                    {"role": t.role, "content": t.content, "time": t.time}
                    for t in turns
                ]
            }


def create_app(
    model_path: Optional[str] = None,
    data_dir: str = "./.rfsn_api",
) -> "FastAPI":
    """Create and configure the FastAPI application."""
    server = RFSNAPIServer(
        model_path=model_path,
        data_dir=data_dir,
        enable_llm=model_path is not None,
    )
    return server.app


def main():
    """Run the API server from command line."""
    if not FASTAPI_AVAILABLE:
        print("FastAPI not installed. Install with:")
        print("  pip install fastapi uvicorn")
        return
    
    import uvicorn
    
    parser = argparse.ArgumentParser(description="RFSN API Server")
    parser.add_argument("--model", help="Path to GGUF model (optional for mock mode)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--data-dir", default="./.rfsn_api", help="Data directory")
    args = parser.parse_args()
# Helper for cli execution
def create_app(model_path: str = None, data_dir: str = "data"):
    # Since ENGINE is global and already instantiated, we might just confuse things if we try to re-init it.
    # Ideally, we should configure the global engine here if model_path is provided.
    if model_path:
        ENGINE.model_path = model_path
        # Re-init LLM if possible, or just accept mock.
        pass
    
    server = RFSNAPIServer(data_dir=data_dir)
    return server.app

# Global instance for uvicorn
server = RFSNAPIServer()
app = server.app

def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="RFSN Hybrid Engine API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--model", type=str, default=None, help="Path to GGUF model")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    args = parser.parse_args()
    
    app = create_app(model_path=args.model, data_dir=args.data_dir)
    
    print(f"\n🚀 RFSN API Server starting on http://{args.host}:{args.port}")
    print(f"📚 API docs: http://{args.host}:{args.port}/docs")
    if not args.model:
        print("⚠️  Running in mock mode (no LLM loaded)")
    print()
    
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
