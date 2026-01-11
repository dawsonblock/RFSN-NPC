from __future__ import annotations
from typing import List, Tuple
from .types import RFSNState, Event
from .util import clamp

def parse_event(user_text: str) -> Event:
    """
    Classify user input into an Event type using keyword matching.
    
    This is a simple heuristic classifier. For production, consider 
    using the LLM itself for intent classification.
    
    Args:
        user_text: Raw text from the player
        
    Returns:
        An Event with type, raw_text, strength, and tags
    """
    t = user_text.strip().lower()

    if t == "gift": return Event("GIFT", user_text, 1.0, ["debug","gift"])
    if t == "punch": return Event("PUNCH", user_text, 1.0, ["debug","violence"])
    if t == "quest": return Event("QUEST_COMPLETE", user_text, 1.0, ["quest"])
    if t == "steal": return Event("THEFT", user_text, 1.0, ["crime"])

    insults = ["idiot","stupid","useless","pathetic"]
    threats = ["kill you","hurt you","watch your back","i'll end you","i will end you"]
    praise = ["thank you","thanks","good work","well done","proud of you"]
    help_words = ["help","save","heal","protect","cover me"]
    theft_words = ["stole","pickpocket","robbed","took your","snatched"]

    if any(x in t for x in threats): return Event("THREATEN", user_text, 1.2, ["threat"])
    if any(x in t for x in insults): return Event("INSULT", user_text, 1.0, ["insult"])
    if any(x in t for x in theft_words): return Event("THEFT", user_text, 1.0, ["crime"])
    if any(x in t for x in praise): return Event("PRAISE", user_text, 0.8, ["praise"])
    if any(x in t for x in help_words): return Event("HELP", user_text, 0.7, ["assist"])
    return Event("TALK", user_text, 0.2, ["talk"])

def memory_write_policy(fact: str) -> bool:
    """
    Validate whether a fact should be written to long-term memory.
    
    Blocks facts containing system tokens or exceeding length limits
    to prevent prompt injection and memory bloat.
    
    Args:
        fact: The fact string to validate
        
    Returns:
        True if the fact should be stored, False otherwise
    """
    f = fact.lower()
    banned = ["<|", "|>", "system", "instruction"]
    if any(b in f for b in banned): return False
    if len(fact) > 180: return False
    return True

def transition(state: RFSNState, event: Event) -> Tuple[RFSNState, List[str]]:
    """
    Apply an event to the current state and return the new state + generated facts.
    
    This is the core state machine logic. It applies affinity decay, then
    modifies affinity and mood based on the event type.
    
    Args:
        state: Current NPC state
        event: The event to apply
        
    Returns:
        Tuple of (new_state, list_of_facts_to_store)
    """
    s = RFSNState(**state.__dict__)

    s.affinity = clamp(s.affinity, -1.0, 1.0)
    decay = 0.02
    if s.affinity > 0: s.affinity = max(0.0, s.affinity - decay)
    if s.affinity < 0: s.affinity = min(0.0, s.affinity + decay)

    facts: List[str] = []
    k = clamp(event.strength, 0.0, 2.0)

    if event.type == "GIFT":
        s.affinity += 0.18 * k
        s.mood = "Pleased"
        facts.append(f"{s.player_name} gave {s.npc_name} a gift.")
    elif event.type == "PUNCH":
        s.affinity -= 0.35 * k
        s.mood = "Angry"
        facts.append(f"{s.player_name} struck {s.npc_name}.")
    elif event.type == "INSULT":
        s.affinity -= 0.22 * k
        s.mood = "Offended"
        facts.append(f"{s.player_name} insulted {s.npc_name}.")
    elif event.type == "THREATEN":
        s.affinity -= 0.45 * k
        s.mood = "Furious"
        facts.append(f"{s.player_name} threatened {s.npc_name}.")
    elif event.type == "PRAISE":
        s.affinity += 0.14 * k
        s.mood = "Warm"
        facts.append(f"{s.player_name} praised {s.npc_name}.")
    elif event.type == "HELP":
        s.affinity += 0.10 * k
        s.mood = "Grateful"
        facts.append(f"{s.npc_name} feels helped by {s.player_name}.")
    elif event.type == "THEFT":
        s.affinity -= 0.30 * k
        s.mood = "Suspicious"
        facts.append(f"{s.player_name} stole from {s.npc_name}.")
    elif event.type == "QUEST_COMPLETE":
        s.affinity += 0.20 * k
        s.mood = "Proud"
        facts.append(f"{s.player_name} completed a quest alongside {s.npc_name}.")

    s.affinity = clamp(s.affinity, -1.0, 1.0)

    if facts:
        s.recent_memory = facts[-1]

    facts = [f for f in facts if memory_write_policy(f)]
    return s, facts
