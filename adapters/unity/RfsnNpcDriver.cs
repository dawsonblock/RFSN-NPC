using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace RFSN
{
    /// <summary>
    /// Example NPC driver that demonstrates how to use RfsnEventPublisher.
    /// 
    /// This component shows trigger-based event publishing for common NPC scenarios.
    /// Attach to your NPC GameObjects and configure the triggers.
    /// 
    /// Usage:
    /// 1. Attach to NPC GameObject
    /// 2. Ensure NPC has a Collider with "Is Trigger" checked
    /// 3. Tag player GameObject with "Player"
    /// 4. Configure npcId to match NPC name in RFSN system
    /// </summary>
    [RequireComponent(typeof(Collider))]
    public class RfsnNpcDriver : MonoBehaviour
    {
        [Header("NPC Configuration")]
        [Tooltip("Unique identifier for this NPC in RFSN system")]
        public string npcId = "lydia";
        
        [Header("Detection Settings")]
        [Tooltip("Tag used to identify player")]
        public string playerTag = "Player";
        
        [Tooltip("Distance at which NPC detects player")]
        public float detectionRadius = 5.0f;
        
        [Header("Combat Settings")]
        [Tooltip("HP threshold to trigger combat_start event")]
        public float combatStartHealthThreshold = 0.9f;
        
        private RfsnEventPublisher eventPublisher;
        private bool playerNearby = false;
        private bool inCombat = false;
        private float initialHealth;
        private float currentHealth;
        
        void Start()
        {
            // Find or create event publisher
            eventPublisher = FindObjectOfType<RfsnEventPublisher>();
            if (eventPublisher == null)
            {
                Debug.LogError("[RFSN] No RfsnEventPublisher found in scene!");
                enabled = false;
                return;
            }
            
            // Initialize health tracking
            initialHealth = 100f; // Replace with actual health system
            currentHealth = initialHealth;
        }
        
        void Update()
        {
            // Check for player proximity (if not using triggers)
            GameObject player = GameObject.FindGameObjectWithTag(playerTag);
            if (player != null)
            {
                float distance = Vector3.Distance(transform.position, player.transform.position);
                
                // Player entered detection radius
                if (distance <= detectionRadius && !playerNearby)
                {
                    OnPlayerNearby(player);
                }
                // Player left detection radius
                else if (distance > detectionRadius && playerNearby)
                {
                    OnPlayerLeft(player);
                }
            }
        }
        
        /// <summary>
        /// Called when player enters trigger collider.
        /// </summary>
        void OnTriggerEnter(Collider other)
        {
            if (other.CompareTag(playerTag))
            {
                OnPlayerNearby(other.gameObject);
            }
        }
        
        /// <summary>
        /// Called when player exits trigger collider.
        /// </summary>
        void OnTriggerExit(Collider other)
        {
            if (other.CompareTag(playerTag))
            {
                OnPlayerLeft(other.gameObject);
            }
        }
        
        /// <summary>
        /// Handle player entering detection range.
        /// </summary>
        private void OnPlayerNearby(GameObject player)
        {
            if (playerNearby) return;
            
            playerNearby = true;
            eventPublisher.PublishPlayerNearby(npcId);
            
            Debug.Log($"[RFSN] {npcId}: Player detected");
        }
        
        /// <summary>
        /// Handle player leaving detection range.
        /// </summary>
        private void OnPlayerLeft(GameObject player)
        {
            if (!playerNearby) return;
            
            playerNearby = false;
            eventPublisher.PublishPlayerLeft(npcId);
            
            Debug.Log($"[RFSN] {npcId}: Player left");
        }
        
        /// <summary>
        /// Call this when NPC takes damage.
        /// Hook this into your damage system.
        /// </summary>
        /// <param name="damage">Amount of damage taken</param>
        /// <param name="attacker">GameObject that dealt damage</param>
        public void TakeDamage(float damage, GameObject attacker)
        {
            currentHealth -= damage;
            
            // Start combat if not already in combat
            if (!inCombat && currentHealth < initialHealth * combatStartHealthThreshold)
            {
                inCombat = true;
                string enemyName = attacker != null ? attacker.name : "Unknown";
                eventPublisher.PublishCombatStart(npcId, enemyName);
                
                Debug.Log($"[RFSN] {npcId}: Combat started with {enemyName}");
            }
            
            // Publish damage event
            var payload = new Dictionary<string, object>
            {
                { "damage", damage },
                { "attacker", attacker != null ? attacker.name : "Unknown" }
            };
            float magnitude = Mathf.Clamp01(damage / 50.0f);
            eventPublisher.PublishEvent("combat_hit_taken", npcId, magnitude, payload);
        }
        
        /// <summary>
        /// Call this when combat ends.
        /// </summary>
        /// <param name="victory">True if NPC won, false otherwise</param>
        public void EndCombat(bool victory)
        {
            if (!inCombat) return;
            
            inCombat = false;
            eventPublisher.PublishCombatEnd(npcId, victory);
            
            Debug.Log($"[RFSN] {npcId}: Combat ended, victory={victory}");
        }
        
        /// <summary>
        /// Call this when player gives item to NPC.
        /// Hook this into your inventory/gift system.
        /// </summary>
        /// <param name="itemName">Name of item</param>
        /// <param name="itemValue">Value in gold/credits</param>
        public void ReceiveItem(string itemName, int itemValue)
        {
            eventPublisher.PublishItemReceived(npcId, itemName, itemValue);
            
            Debug.Log($"[RFSN] {npcId}: Received {itemName} (value: {itemValue})");
        }
        
        /// <summary>
        /// Call this when quest is completed.
        /// Hook this into your quest system.
        /// </summary>
        /// <param name="questName">Name of completed quest</param>
        public void CompleteQuest(string questName)
        {
            eventPublisher.PublishQuestCompleted(npcId, questName);
            
            Debug.Log($"[RFSN] {npcId}: Quest completed: {questName}");
        }
        
        /// <summary>
        /// Example: Custom event for mod-specific behavior.
        /// </summary>
        public void PublishCustomEvent(string eventType, float magnitude, Dictionary<string, object> data = null)
        {
            eventPublisher.PublishEvent(eventType, npcId, magnitude, data);
        }
        
        /// <summary>
        /// Draw detection radius in Scene view.
        /// </summary>
        void OnDrawGizmosSelected()
        {
            Gizmos.color = playerNearby ? Color.green : Color.yellow;
            Gizmos.DrawWireSphere(transform.position, detectionRadius);
        }
    }
}
