from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from .engine import ENGINE
from .version import __version__

# ... (rest of imports/models)

class ChatRequest(BaseModel):
    message: str
    player_name: str = "Player"

class RFSNAPIServer:
    def __init__(self) -> None:
        self.app = FastAPI(title="RFSN Hybrid", version=__version__)
        self._mount_routes()
        self._mount_ui()

    def _mount_ui(self) -> None:
        # Determine path to ui directory relative to this file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.join(base_dir, "ui")
        
        # Mount the UI file specifically or directory
        if os.path.exists(ui_dir):
            self.app.mount("/dashboard_assets", StaticFiles(directory=ui_dir), name="ui_assets")
            
            @self.app.get("/ui")
            def dashboard():
                return FileResponse(os.path.join(ui_dir, "index.html"))
        else:
            print(f"Warning: UI directory not found at {ui_dir}")

    def _mount_routes(self) -> None:
        @self.app.get("/health")
        def health():
            return {"ok": True}

        @self.app.get("/")
        def root():
            # Return info but also hint at UI
            return {
                "name": "RFSN Hybrid", 
                "version": __version__,
                "dashboard": "/ui"
            }

        @self.app.post("/npc/{npc_id}/chat")
        def chat(npc_id: str, req: ChatRequest):
            return ENGINE.handle_message(npc_id=npc_id, text=req.message, user_name=req.player_name)

        @self.app.get("/npc/{npc_id}/history")
        def get_history(npc_id: str):
            store = ENGINE.get_store(npc_id)
            return {"history": store.get_history()}

        @self.app.post("/npc/{npc_id}/reset")
        def reset(npc_id: str):
            # Access engine internals to clear logic
            # Since ENGINE implementation doesn't have an explicit delete, we access _stores
            if npc_id in ENGINE._stores:
                del ENGINE._stores[npc_id]
            return {"status": "reset", "npc_id": npc_id}

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
