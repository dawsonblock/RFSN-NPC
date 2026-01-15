"""
Unity game engine adapter for RFSN environment feedback.

This module provides documentation and examples for integrating
RFSN with Unity games via HTTP.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from ..event_schema import EnvironmentEvent

logger = logging.getLogger(__name__)


class UnityAdapter:
    """
    Adapter for Unity game engine integration.
    
    Unity can easily make HTTP requests, so this adapter
    primarily provides documentation and helper methods.
    
    Integration approach:
    1. Unity C# script posts events to RFSN API endpoint
    2. RFSN server processes events and updates NPC state
    3. Unity polls or receives responses with NPC behavior
    """
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """
        Initialize Unity adapter.
        
        Args:
            api_base_url: Base URL for RFSN API server
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.event_endpoint = f"{self.api_base_url}/env/event"
    
    def get_integration_instructions(self) -> str:
        """Get integration instructions for Unity developers."""
        return UNITY_INTEGRATION_INSTRUCTIONS
    
    def get_csharp_example(self) -> str:
        """Get example C# script for Unity."""
        return UNITY_CSHARP_EXAMPLE
    
    def validate_event(self, event: EnvironmentEvent) -> tuple[bool, Optional[str]]:
        """
        Validate an event before sending to RFSN.
        
        Args:
            event: Event to validate
            
        Returns:
            (is_valid, error_message)
        """
        return event.validate()


# Unity C# Example Code
UNITY_CSHARP_EXAMPLE = """
[See full C# example in documentation]
Minimal Unity sender:

using UnityEngine;
using UnityEngine.Networking;
using System.Collections;

public class RFSNSender : MonoBehaviour {
    public string serverUrl = "http://localhost:8000/env/event";
    
    public void SendEvent(string eventType, string npcId) {
        StartCoroutine(PostEvent(eventType, npcId));
    }
    
    IEnumerator PostEvent(string eventType, string npcId) {
        string json = "{\\\"event_type\\\":\\\"" + eventType + 
                      "\\\",\\\"npc_id\\\":\\\"" + npcId + 
                      "\\\",\\\"player_id\\\":\\\"player_1\\\"}";
        byte[] data = System.Text.Encoding.UTF8.GetBytes(json);
        
        using (UnityWebRequest req = new UnityWebRequest(serverUrl, "POST")) {
            req.uploadHandler = new UploadHandlerRaw(data);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            yield return req.SendWebRequest();
            
            if (req.result == UnityWebRequest.Result.Success) {
                Debug.Log("Event sent: " + eventType);
            }
        }
    }
}
"""

UNITY_INTEGRATION_INSTRUCTIONS = """
Unity Integration Guide for RFSN:
1. Start RFSN server: python -m rfsn_hybrid.api
2. Add RFSNSender script to Unity GameObject
3. Call SendEvent from dialogue/combat/quest systems
4. Events are POST to http://localhost:8000/env/event as JSON
"""
