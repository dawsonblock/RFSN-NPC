from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest
from rfsn_hybrid.api import app, ENGINE

def test_chat_route_calls_engine(monkeypatch):
    """
    Verify that calling POST /npc/{id}/chat actually delegates to ENGINE.handle_message.
    This ensures we don't accidentally bypass the engine in the API (e.g. by using legacy code).
    """
    # 1. Mock the engine method
    mock_handle = MagicMock(return_value={
        "text": "Mock Engine Response",
        "state": {
            "npc_name": "MockNPC", 
            "affinity": 0.5, 
            "mood": "Neutral",
            "role": "Tester",
            "player_name": "Player",
            "player_playstyle": "Adventurer"
        },
        "facts_used": []
    })
    
    # Apply monkeypatch to the global ENGINE instance
    monkeypatch.setattr(ENGINE, "handle_message", mock_handle)

    client = TestClient(app)
    
    # 2. Call the API
    payload = {"message": "Hello world", "player_name": "Tester"}
    response = client.post("/npc/test_npc/chat", json=payload)
    
    # 3. Assertions
    assert response.status_code == 200, f"API failed: {response.text}"
    data = response.json()
    assert data["response"] == "Mock Engine Response"
    
    # Verify the mock was called exactly once with expected args
    mock_handle.assert_called_once()
    call_args = mock_handle.call_args
    assert call_args.kwargs["npc_id"] == "test_npc"
    assert call_args.kwargs["text"] == "Hello world"
    assert call_args.kwargs["user_name"] == "Tester"
