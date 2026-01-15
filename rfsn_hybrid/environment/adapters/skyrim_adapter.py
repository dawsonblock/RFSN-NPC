"""
Skyrim game engine adapter for RFSN environment feedback.

This module provides documentation and examples for integrating
RFSN with Skyrim mods via HTTP or file-drop polling.
"""
from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..event_schema import EnvironmentEvent

logger = logging.getLogger(__name__)


class SkyrimAdapter:
    """
    Adapter for Skyrim (Papyrus) integration.
    
    Skyrim modding has limited HTTP support, so we provide two options:
    1. HTTP POST via SKSE plugin (recommended if available)
    2. File-drop polling (fallback for pure Papyrus)
    
    File-drop approach:
    - Papyrus writes JSON events to a watched directory
    - RFSN server polls this directory and processes events
    - Simple but introduces slight latency
    """
    
    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        file_drop_dir: Optional[str] = None,
    ):
        """
        Initialize Skyrim adapter.
        
        Args:
            api_base_url: Base URL for RFSN API (HTTP method)
            file_drop_dir: Directory to watch for event files (file-drop method)
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.event_endpoint = f"{self.api_base_url}/env/event"
        self.file_drop_dir = Path(file_drop_dir) if file_drop_dir else None
        
        if self.file_drop_dir:
            self.file_drop_dir.mkdir(parents=True, exist_ok=True)
    
    def get_integration_instructions(self) -> str:
        """Get integration instructions for Skyrim modders."""
        return SKYRIM_INTEGRATION_INSTRUCTIONS
    
    def get_papyrus_example(self) -> str:
        """Get example Papyrus code."""
        return SKYRIM_PAPYRUS_EXAMPLE
    
    def poll_file_drop(self) -> List[EnvironmentEvent]:
        """
        Poll file-drop directory for new events.
        
        Returns:
            List of parsed events
        """
        if not self.file_drop_dir:
            return []
        
        events = []
        
        for file_path in self.file_drop_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    event_data = json.load(f)
                
                event = EnvironmentEvent.from_dict(event_data)
                is_valid, error = event.validate()
                
                if is_valid:
                    events.append(event)
                    # Delete processed file
                    file_path.unlink()
                else:
                    logger.warning(f"Invalid event in {file_path}: {error}")
                    # Move to error directory
                    error_dir = self.file_drop_dir / "errors"
                    error_dir.mkdir(exist_ok=True)
                    file_path.rename(error_dir / file_path.name)
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
        
        return events
    
    def start_file_watcher(self, callback):
        """
        Start a background thread that watches for new event files.
        
        Args:
            callback: Function to call with each new event
        """
        if not self.file_drop_dir:
            raise ValueError("file_drop_dir must be set to use file watcher")
        
        import threading
        import time
        
        def watch_loop():
            while True:
                events = self.poll_file_drop()
                for event in events:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")
                time.sleep(1.0)  # Poll every second
        
        thread = threading.Thread(target=watch_loop, daemon=True)
        thread.start()
        logger.info(f"Started file watcher on {self.file_drop_dir}")


# Skyrim/Papyrus integration examples

SKYRIM_PAPYRUS_EXAMPLE = """
; Papyrus script example for RFSN integration
; This shows how to emit events that RFSN can consume

Scriptname RFSNEventEmitter extends Quest

; Configuration
String Property EventFilePath = "Data/SKSE/Plugins/RFSN/events/" Auto
String Property NPCId Auto  ; Set in CK

; Helper to write event to file
Function EmitEvent(String eventType, String payload = "") Global
    ; Generate unique filename
    String timestamp = Utility.GetCurrentRealTime() as String
    String filename = eventType + "_" + timestamp + ".json"
    String fullPath = EventFilePath + filename
    
    ; Build JSON (simple string concat for Papyrus)
    String json = "{"
    json += "\\"event_type\\":\\"" + eventType + "\\","
    json += "\\"npc_id\\":\\"" + NPCId + "\\","
    json += "\\"player_id\\":\\"player_1\\","
    json += "\\"ts\\":" + Utility.GetCurrentRealTime() + ","
    json += "\\"payload\\":{" + payload + "}"
    json += "}"
    
    ; Write to file (requires SKSE file functions)
    MiscUtil.WriteToFile(fullPath, json, false, false)
EndFunction

; Event handlers - call these from your dialogue/quest scripts

Function OnDialogueStart()
    EmitEvent("dialogue_started")
EndFunction

Function OnCombatEnd(Bool playerWon)
    String result = "loss"
    If playerWon
        result = "win"
    EndIf
    String payload = "\\"result\\":\\"" + result + "\\""
    EmitEvent("combat_result", payload)
EndFunction

Function OnQuestComplete(String questId)
    String payload = "\\"quest_id\\":\\"" + questId + "\\",\\"status\\":\\"completed\\""
    EmitEvent("quest_completed", payload)
EndFunction

Function OnGiftReceived(String itemName, Int itemValue)
    String payload = "\\"item_id\\":\\"" + itemName + "\\",\\"item_value\\":" + itemValue
    EmitEvent("gift", payload)
EndFunction
"""

SKYRIM_INTEGRATION_INSTRUCTIONS = """
Skyrim Integration with RFSN

Method 1: File-Drop (Recommended for Papyrus-only)
1. Configure RFSN to watch a directory:
   rfsn_hybrid/environment/adapters/skyrim_adapter.py
   SkyrimAdapter(file_drop_dir="C:/path/to/skyrim/Data/SKSE/Plugins/RFSN/events")

2. In Papyrus scripts, write JSON event files to this directory
3. RFSN polls and processes events automatically

Method 2: HTTP POST (Requires SKSE plugin with HTTP support)
1. Use an SKSE plugin that supports HTTP (e.g., PapyrusUtil with HTTP extensions)
2. POST JSON events to http://localhost:8000/env/event
3. Lower latency than file-drop

Event Mapping:
- Dialogue Start/End -> dialogue_started, dialogue_ended
- Combat Start/End -> combat_started, combat_result
- Quest Updates -> quest_started, quest_completed, quest_failed
- Proximity -> Use trigger volumes, emit proximity_update
- Gifts -> OnItemAdded event, emit gift

Directory Structure:
Skyrim/Data/SKSE/Plugins/RFSN/
├── events/          # Drop JSON files here
└── errors/          # Invalid events moved here

Example Event File:
{
  "event_type": "dialogue_started",
  "npc_id": "lydia_001",
  "player_id": "player_1",
  "ts": 1705350000.0,
  "payload": {}
}
"""
