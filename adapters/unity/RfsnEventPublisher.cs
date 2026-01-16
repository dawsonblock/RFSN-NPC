using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

namespace RFSN
{
    /// <summary>
    /// Unity component for publishing game events to RFSN-NPC API.
    /// 
    /// Features:
    /// - Event batching to reduce API calls
    /// - Automatic throttling
    /// - Priority queue for important events
    /// - Coroutine-based async HTTP
    /// 
    /// Usage:
    /// 1. Attach to a GameObject in your scene
    /// 2. Configure apiUrl to point to your RFSN server
    /// 3. Call PublishEvent() from your game logic
    /// </summary>
    public class RfsnEventPublisher : MonoBehaviour
    {
        [Header("Configuration")]
        [Tooltip("Base URL of RFSN API server")]
        public string apiUrl = "http://localhost:8000";
        
        [Tooltip("Maximum events to batch before sending")]
        [Range(1, 20)]
        public int batchSize = 5;
        
        [Tooltip("Minimum seconds between API calls")]
        [Range(0.5f, 5.0f)]
        public float throttleSeconds = 1.0f;
        
        [Header("Debug")]
        [Tooltip("Log all events to console")]
        public bool debugLogging = false;
        
        // Internal state
        private Queue<RfsnEvent> eventQueue = new Queue<RfsnEvent>();
        private float lastSendTime = 0f;
        private bool isSending = false;
        
        /// <summary>
        /// Represents a game event to send to RFSN.
        /// </summary>
        [Serializable]
        public class RfsnEvent
        {
            public string event_type;
            public string npc_id;
            public string player_id = "Player";
            public float magnitude = 0.5f;
            public double ts;
            public Dictionary<string, object> payload;
            public int version = 1;
            
            public RfsnEvent(string eventType, string npcId)
            {
                event_type = eventType;
                npc_id = npcId;
                ts = (DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds;
                payload = new Dictionary<string, object>();
            }
        }
        
        void Update()
        {
            // Periodically flush queued events if throttle allows
            if (eventQueue.Count > 0 && 
                Time.time - lastSendTime >= throttleSeconds &&
                !isSending)
            {
                StartCoroutine(FlushEvents());
            }
        }
        
        /// <summary>
        /// Publish an event to RFSN API.
        /// </summary>
        /// <param name="eventType">Type of event (e.g., "combat_start")</param>
        /// <param name="npcId">ID of affected NPC</param>
        /// <param name="magnitude">Event intensity (0.0 to 1.0)</param>
        /// <param name="payload">Additional event data</param>
        /// <param name="priority">If true, send immediately without batching</param>
        public void PublishEvent(
            string eventType,
            string npcId,
            float magnitude = 0.5f,
            Dictionary<string, object> payload = null,
            bool priority = false)
        {
            var rfsnEvent = new RfsnEvent(eventType, npcId)
            {
                magnitude = Mathf.Clamp01(magnitude),
                payload = payload ?? new Dictionary<string, object>()
            };
            
            if (debugLogging)
            {
                Debug.Log($"[RFSN] Publishing event: {eventType} for {npcId}");
            }
            
            if (priority)
            {
                StartCoroutine(SendEventImmediate(rfsnEvent));
            }
            else
            {
                eventQueue.Enqueue(rfsnEvent);
                
                // Auto-flush if batch is full
                if (eventQueue.Count >= batchSize && !isSending)
                {
                    StartCoroutine(FlushEvents());
                }
            }
        }
        
        /// <summary>
        /// Send a single event immediately (for priority events).
        /// </summary>
        private IEnumerator SendEventImmediate(RfsnEvent rfsnEvent)
        {
            yield return SendEvent(rfsnEvent);
        }
        
        /// <summary>
        /// Flush all queued events to API.
        /// </summary>
        private IEnumerator FlushEvents()
        {
            if (isSending || eventQueue.Count == 0)
                yield break;
            
            isSending = true;
            
            // Send all queued events
            while (eventQueue.Count > 0)
            {
                var rfsnEvent = eventQueue.Dequeue();
                yield return SendEvent(rfsnEvent);
            }
            
            lastSendTime = Time.time;
            isSending = false;
        }
        
        /// <summary>
        /// Send a single event via HTTP POST.
        /// </summary>
        private IEnumerator SendEvent(RfsnEvent rfsnEvent)
        {
            string url = $"{apiUrl}/env/event";
            string jsonData = JsonUtility.ToJson(rfsnEvent);
            
            using (UnityWebRequest request = UnityWebRequest.Post(url, ""))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                
                yield return request.SendWebRequest();
                
                if (request.result == UnityWebRequest.Result.Success)
                {
                    if (debugLogging)
                    {
                        Debug.Log($"[RFSN] Event sent successfully: {rfsnEvent.event_type}");
                    }
                }
                else
                {
                    Debug.LogError($"[RFSN] Failed to send event: {request.error}");
                }
            }
        }
        
        /// <summary>
        /// Helper methods for common event types.
        /// </summary>
        
        public void PublishCombatStart(string npcId, string enemyName)
        {
            var payload = new Dictionary<string, object>
            {
                { "enemy", enemyName }
            };
            PublishEvent("combat_start", npcId, 0.7f, payload, priority: true);
        }
        
        public void PublishCombatEnd(string npcId, bool victory)
        {
            var payload = new Dictionary<string, object>
            {
                { "victory", victory }
            };
            float magnitude = victory ? 0.8f : 0.5f;
            PublishEvent("combat_end", npcId, magnitude, payload, priority: true);
        }
        
        public void PublishItemReceived(string npcId, string itemName, int itemValue)
        {
            var payload = new Dictionary<string, object>
            {
                { "item", itemName },
                { "value", itemValue }
            };
            float magnitude = Mathf.Min(1.0f, 0.1f + (itemValue / 1000.0f) * 0.9f);
            PublishEvent("item_received", npcId, magnitude, payload);
        }
        
        public void PublishQuestCompleted(string npcId, string questName)
        {
            var payload = new Dictionary<string, object>
            {
                { "quest", questName }
            };
            PublishEvent("quest_completed", npcId, 0.9f, payload, priority: true);
        }
        
        public void PublishPlayerNearby(string npcId)
        {
            PublishEvent("player_nearby", npcId, 0.3f);
        }
        
        public void PublishPlayerLeft(string npcId)
        {
            PublishEvent("player_left", npcId, 0.2f);
        }
    }
}
