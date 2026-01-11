"""
REST API server for RFSN Hybrid Engine.

Provides HTTP endpoints for game integration, allowing external
applications to interact with NPCs without loading Python directly.

Run with:
    python -m rfsn_hybrid.api --model /path/to/model.gguf

Requires: pip install fastapi uvicorn
"""
from __future__ import annotations

import os
import time
import logging
import argparse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Check for FastAPI
try:
    from fastapi import FastAPI, HTTPException, Query, Body
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .types import RFSNState
from .state_machine import parse_event, transition
from .storage import ConversationMemory, FactsStore
from .config import NPCConfig, ConfigManager, get_preset, list_presets


# ============================================================================
# Pydantic Models for API
# ============================================================================

if FASTAPI_AVAILABLE:
    
    class ChatRequest(BaseModel):
        """Request body for chat endpoint."""
        message: str = Field(..., description="Player's message to the NPC")
        player_name: str = Field("Player", description="Name of the player")
    
    class ChatResponse(BaseModel):
        """Response from chat endpoint."""
        response: str = Field(..., description="NPC's response")
        npc_name: str
        affinity: float
        mood: str
        attitude: str
        latency_ms: float
        event_type: str
        facts_used: List[str] = []
    
    class NPCStatus(BaseModel):
        """NPC status information."""
        name: str
        role: str
        affinity: float
        mood: str
        attitude: str
        conversation_turns: int
        facts_count: int
    
    class NPCCreateRequest(BaseModel):
        """Request to create or reset an NPC."""
        preset: Optional[str] = Field(None, description="Built-in preset name")
        name: str = Field("Lydia", description="NPC name")
        role: str = Field("Housecarl", description="NPC role")
        initial_affinity: float = Field(0.5, ge=-1.0, le=1.0)
        initial_mood: str = Field("Neutral")


# ============================================================================
# API Server
# ============================================================================

class NPCSession:
    """Manages state for a single NPC session."""
    
    def __init__(
        self,
        npc_id: str,
        state: RFSNState,
        memory: ConversationMemory,
        facts: FactsStore,
        data_dir: str,
    ):
        self.npc_id = npc_id
        self.state = state
        self.memory = memory
        self.facts = facts
        self.data_dir = data_dir
        self.state_path = os.path.join(data_dir, f"{npc_id}_state.json")
    
    def save(self):
        """Persist state to disk."""
        self.state.save(self.state_path)


class RFSNAPIServer:
    """
    FastAPI-based REST server for RFSN Hybrid Engine.
    
    Manages multiple NPC sessions and provides endpoints for:
    - Chat with NPCs
    - NPC status/state queries
    - NPC creation/reset
    - Preset management
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        data_dir: str = "./.rfsn_api",
        enable_llm: bool = True,
    ):
        """
        Initialize the API server.
        
        Args:
            model_path: Path to GGUF model (None for mock responses)
            data_dir: Directory for NPC data persistence
            enable_llm: Whether to load and use the LLM
        """
        if not FASTAPI_AVAILABLE:
            raise ImportError(
                "FastAPI not installed. Install with: pip install fastapi uvicorn"
            )
        
        self.model_path = model_path
        self.data_dir = data_dir
        self.enable_llm = enable_llm
        self.sessions: Dict[str, NPCSession] = {}
        self.engine = None
        
        os.makedirs(data_dir, exist_ok=True)
        
        # Load LLM if requested
        if enable_llm and model_path:
            self._load_engine()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="RFSN Hybrid Engine API",
            description="REST API for NPC dialogue with state machine + local LLM",
            version="0.4.1",
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
    
    def _load_engine(self):
        """Load the LLM engine."""
        from .engine import RFSNHybridEngine
        self.engine = RFSNHybridEngine(
            model_path=self.model_path,
            verbose=False,
        )
        logger.info(f"Loaded LLM: {self.model_path}")
    
    def _get_or_create_session(self, npc_id: str) -> NPCSession:
        """Get existing session or create new one."""
        if npc_id in self.sessions:
            return self.sessions[npc_id]
        
        # Try to load from preset
        config = get_preset(npc_id)
        if config:
            state = RFSNState(
                npc_name=config.name,
                role=config.role,
                affinity=config.initial_affinity,
                mood=config.initial_mood,
                player_name="Player",
                player_playstyle="Adventurer",
            )
        else:
            # Default NPC
            state = RFSNState(
                npc_name=npc_id.title(),
                role="NPC",
                affinity=0.5,
                mood="Neutral",
                player_name="Player",
                player_playstyle="Adventurer",
            )
        
        # Check for existing state file
        state_path = os.path.join(self.data_dir, f"{npc_id}_state.json")
        loaded = RFSNState.load(state_path)
        if loaded:
            state = loaded
        
        # Create session
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
        return session
    
    def _register_routes(self):
        """Register all API routes."""
        
        @self.app.get("/")
        async def root():
            """API health check."""
            return {
                "status": "ok",
                "engine": "RFSN Hybrid Engine",
                "version": "0.4.1",
                "llm_loaded": self.engine is not None,
            }
        
        @self.app.get("/presets", response_model=List[str])
        async def get_presets():
            """List available NPC presets."""
            return list_presets()
        
        @self.app.get("/npcs")
        async def list_npcs():
            """List active NPC sessions."""
            return {
                npc_id: {
                    "name": session.state.npc_name,
                    "affinity": session.state.affinity,
                    "mood": session.state.mood,
                }
                for npc_id, session in self.sessions.items()
            }
        
        @self.app.get("/npc/{npc_id}", response_model=NPCStatus)
        async def get_npc_status(npc_id: str):
            """Get NPC status."""
            session = self._get_or_create_session(npc_id)
            return NPCStatus(
                name=session.state.npc_name,
                role=session.state.role,
                affinity=session.state.affinity,
                mood=session.state.mood,
                attitude=session.state.attitude(),
                conversation_turns=len(session.memory.turns),
                facts_count=len(session.facts.facts),
            )
        
        @self.app.post("/npc/{npc_id}/chat", response_model=ChatResponse)
        async def chat_with_npc(npc_id: str, request: ChatRequest):
            """Send a message to an NPC and get a response."""
            session = self._get_or_create_session(npc_id)
            
            # Update player name if provided
            if request.player_name:
                session.state.player_name = request.player_name
            
            # Parse event and transition state
            event = parse_event(request.message)
            session.state, new_facts = transition(session.state, event)
            
            # Store new facts
            tags = (event.tags or []) + [event.type.lower()]
            for f in new_facts:
                session.facts.add_fact(f, tags, 0.7)
            
            # Generate response
            t0 = time.time()
            if self.engine:
                result = self.engine.generate(
                    user_text=request.message,
                    state=session.state,
                    memory=session.memory,
                    facts=session.facts,
                    fact_tags=event.tags or [],
                )
                response_text = result["text"]
                facts_used = result.get("facts_used", [])
            else:
                # Mock response if no LLM
                response_text = f"*{session.state.npc_name} nods* I hear you, {request.player_name}."
                facts_used = []
                session.memory.add("user", request.message)
                session.memory.add("assistant", response_text)
            
            latency_ms = (time.time() - t0) * 1000
            
            # Save state
            session.save()
            
            return ChatResponse(
                response=response_text,
                npc_name=session.state.npc_name,
                affinity=session.state.affinity,
                mood=session.state.mood,
                attitude=session.state.attitude(),
                latency_ms=latency_ms,
                event_type=event.type,
                facts_used=facts_used,
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
    
    app = create_app(model_path=args.model, data_dir=args.data_dir)
    
    print(f"\n🚀 RFSN API Server starting on http://{args.host}:{args.port}")
    print(f"📚 API docs: http://{args.host}:{args.port}/docs")
    if not args.model:
        print("⚠️  Running in mock mode (no LLM loaded)")
    print()
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
