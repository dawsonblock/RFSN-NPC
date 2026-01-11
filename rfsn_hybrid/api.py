from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel

from .engine import ENGINE
from .version import __version__

class ChatRequest(BaseModel):
    message: str
    player_name: str = "Player"

class RFSNAPIServer:
    def __init__(self) -> None:
        self.app = FastAPI(title="RFSN Hybrid", version=__version__)
        self._mount_routes()

    def _mount_routes(self) -> None:
        @self.app.get("/health")
        def health():
            return {"ok": True}

        @self.app.get("/")
        def root():
            return {"name": "RFSN Hybrid", "version": __version__}

        @self.app.post("/npc/{npc_id}/chat")
        def chat(npc_id: str, req: ChatRequest):
            return ENGINE.handle_message(npc_id=npc_id, text=req.message, user_name=req.player_name)

def create_app():
    return RFSNAPIServer().app

app = create_app()

def main():
    import uvicorn
    # Hardcode port/host as per user request for simplicity, or keep minimal args.
    # User requested: uvicorn.run("rfsn_hybrid.api:app", host="0.0.0.0", port=8000, reload=False)
    uvicorn.run("rfsn_hybrid.api:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
