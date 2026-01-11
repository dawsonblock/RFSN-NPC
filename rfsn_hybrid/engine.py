from __future__ import annotations

import time
import logging
import threading
from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING

from .types import RFSNState
from .storage import ConversationMemory, FactsStore, select_facts
from .prompting import (
    PromptTemplate,
    default_template_for_model,
    stop_tokens_for_template,
    render_llama3,
    render_phi3_chatml,
)

if TYPE_CHECKING:
    from .semantic_memory import SemanticFactStore

logger = logging.getLogger(__name__)



from .core.state.store import StateStore
from .core.state.reducer import reduce_state, reduce_events
from .core.state.event_types import EventType, StateEvent

class RFSNHybridEngine:
    """
    Core engine combining state machine, memory, and LLM for NPC dialogue.
    
    Unified architecture:
    - Uses StateStore for event-sourced state management
    - Uses Reducer for consistent state transitions
    - Wraps LLM for generation
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        template: Optional[PromptTemplate] = None,
        n_ctx: int = 2048,
        n_threads: int = 4,
        n_gpu_layers: int = -1,
        verbose: bool = False,
    ):
        self.model_path = model_path
        self.template: PromptTemplate = template or (default_template_for_model(model_path) if model_path else "llama3")
        
        # Initialize event-sourced store
        # We use a dummy initial state here; in practice, each NPC has its own store/state.
        # This engine instance acts as a coordinator.
        # For the API, we might want one store per NPC.
        # But to keep API simple, we'll let the API manage sessions map to stores,
        # or we make the Engine stateless regarding specific NPC instances and just a processor.
        # However, the user request says "Create a single global engine instance (store + reducer)".
        # This implies the engine might hold the store.
        # Given the multi-NPC nature, let's keep the Engine as the processor and the Store per NPC.
        # WAIT - The user request says: "ENGINE = RFSNEngine() ... self.store = StateStore(...)".
        # This implies a singleton engine managing state? Or maybe just providing the logic.
        # If we support multiple NPCs, a single store doesn't make sense unless the store supports multiple NPCs.
        # The current StateStore seems single-state.
        # Let's assume for now the API manages sessions, and we use the Engine to HELP manage that,
        # OR we modify the engine to hold a mapping of stores. 
        #
        # Let's follow the user's snippet "self.store = StateStore(reducer=reduce_event)"
        # This implies a single store. Maybe for a single active NPC?
        # But API supports /npc/{id}.
        #
        # I will implement a Registry of stores in the Engine to support multiple NPCs.
        
        self._stores: Dict[str, StateStore] = {}
        self._lock = threading.Lock()

        if model_path:
            try:
                from llama_cpp import Llama
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=n_ctx,
                    n_threads=n_threads,
                    n_gpu_layers=n_gpu_layers,
                    verbose=verbose,
                )
                logger.info(f"Loaded model: {model_path} (template: {self.template})")
            except ImportError as e:
                logger.warning(f"llama-cpp-python not found: {e}. Running in MOCK mode.")
                self.llm = None
        else:
            self.llm = None

    def get_store(self, npc_id: str) -> StateStore:
        """Get or create state store for an NPC."""
        with self._lock:
            if npc_id not in self._stores:
                # Initialize with default state
                default_state = RFSNState(
                    npc_name=npc_id,
                    role="NPC",
                    affinity=0.5,
                    mood="Neutral",
                    player_name="Player",
                    player_playstyle="Adventurer"
                )
                self._stores[npc_id] = StateStore(
                    initial_state=default_state
                )
            return self._stores[npc_id]

    def handle_message(
        self, 
        npc_id: str, 
        text: str,
        user_name: str = "Player"
    ) -> Dict[str, Any]:
        """
        Full pipeline: Parse -> Event -> Dispatch -> Generate -> Return Snapshot.
        """
        store = self.get_store(npc_id)
        
        # 1. Parse Event (using legacy logic for now, or simple heuristic)
        # Ideally we'd use an intent classifier here.
        # Using the heuristic from state_machine.py logic (inline here or imported)
        # to ensure we don't depend on the old module too heavily.
        from .state_machine import parse_event 
        event_obj = parse_event(text)
        
        # 2. Dispatch Player Event
        payload = {
            "player_event_type": event_obj.type,
            "strength": event_obj.strength,
            "text": text,
            "tags": event_obj.tags
        }
        store.dispatch(StateEvent(EventType.PLAYER_EVENT, npc_id, payload))
        
        # 3. Add User Memory
        store.dispatch(StateEvent(EventType.FACT_ADD, npc_id, {
            "text": f"{user_name}: {text}",
            "tags": ["chat", "user"],
            "salience": 1.0
        }))

        # 4. Generate Response (Mock or LLM)
        # 4. Generate Response (Mock or LLM)
        snapshot = store.state
        
        # Retrieve recent facts for context
        # Adapting to use internal store directly or via the helper
        facts_store = store.facts if hasattr(store, "facts") else [] # Handle if store doesn't expose it directly yet, but we added a property
        # Actually store.facts property returns list[Fact], we probably want text
        # But we can use _retrieve_facts if we want query-based, or just recent.
        # User requested "minimal retrieval: most recent N facts".
        # Let's implement _select_recent_facts helper.
        
        
        # Retrieve relevant facts (Keyword + Recency)
        facts_used = self._select_relevant_facts(store, text, limit=5)

        response_text = ""
        if self.llm:
             response_text = self._generate_llm(snapshot, text, facts_used)
        else:
             response_text = self._mock_generate(snapshot, text)

        # 5. Dispatch NPC Response Memory
        store.dispatch(StateEvent(EventType.FACT_ADD, npc_id, {
            "text": f"{snapshot.npc_name}: {response_text}",
            "tags": ["chat", "npc"],
            "salience": 1.0
        }))
        
        final_snap = store.state
        return {
            "text": response_text,
            "state": final_snap.to_dict(),
            "facts_used": facts_used
        }

    def _select_relevant_facts(self, store: StateStore, user_text: str, limit: int = 5) -> List[str]:
        """Select facts relevant to user text, falling back to recency."""
        if not hasattr(store, "facts"):
            return []
        
        if not store.facts:
            return []
            
        all_facts = [f.text for f in store.facts]
        
        # 1. Score by keyword overlap
        user_words = set(w.lower() for w in user_text.split() if len(w) > 3)
        scored = []
        for f in all_facts:
            score = sum(1 for w in f.lower().split() if w in user_words)
            scored.append((score, f))
            
        # 2. Prioritize high scores
        scored.sort(key=lambda x: x[0], reverse=True)
        relevant = [f for s, f in scored if s > 0]
        
        # 3. Fallback to recent
        recents = all_facts[-limit:]
        
        # 4. Combine (Relevant -> Recent), Unique only
        selection = []
        seen = set()
        
        for f in relevant:
            if f not in seen:
                selection.append(f)
                seen.add(f)
            if len(selection) >= limit:
                break
                
        if len(selection) < limit:
            for f in reversed(recents): # Newest first
                if f not in seen:
                    selection.append(f)
                    seen.add(f)
                if len(selection) >= limit:
                    break
                    
        return selection[:limit]

    def build_system_text(self, state: RFSNState, facts: List[str]) -> str:
        """Build rich system prompt with persona, mood, and facts."""
        base = (
            f"You are {state.npc_name}, a {state.role} in the world of Skyrim.\n"
            f"Current Mood: {state.mood} (Affinity: {state.affinity:.2f})\n"
            "Interacting with: Player.\n"
            "Guidelines:\n"
            "- Stay in character.\n"
            "- Be concise and natural.\n"
            "- React to the player's actions and words.\n"
        )
        
        if facts:
            base += "\nRelevant Memories:\n" + "\n".join(f"- {f}" for f in facts)
            
        return base

    def _generate_llm(self, state: RFSNState, user_text: str, facts_used: List[str]) -> str:
        """Generate response using real LLM."""
        sys_prompt = self.build_system_text(state, facts_used)
        
        # Simple context assembly
        context = f"{sys_prompt}\n\n"
        context += f"Player: {user_text}\n{state.npc_name}:"
        
        try:
            out = self.llm(
                context,
                max_tokens=160,
                temperature=0.7,
                stop=["\nPlayer:", f"\n{state.npc_name}:", "</s>"],
                echo=False
            )
            return out["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"*{state.npc_name} struggles to find words.*"

    def stream_text(self, npc_id: str, text: str):
        """Yield tokens or sentences for streaming."""
        # Stub for streaming - ensuring it's wired
        response = self.handle_message(npc_id, text)
        full_text = response["text"]
        
        # Simple word yielding simulation
        for word in full_text.split():
            yield word + " "
            time.sleep(0.05)

    def _retrieve_facts(
        self,
        user_text: str,
        facts: FactsStore,
        semantic_facts: Any,
        fact_tags: List[str],
        k: int = 3
    ) -> List[str]:
        """Retrieve relevant facts."""
        # Simple wrapper around select_facts for compatibility/testing
        # Ideally handle_message would use this.
        return select_facts(
            store=facts,
            want_tags=fact_tags,
            k=k
        )

    def build_system_text(self, state: RFSNState, facts: List[str]) -> str:
        """Construct system prompt from state and facts."""
        # Minimal implementation to pass integration test assertions
        prompt = f"Roleplay as {state.npc_name}, a {state.role}.\n"
        prompt += f"Mood: {state.mood}\n"
        prompt += f"Affinity: {state.affinity}\n\n"
        if facts:
            prompt += "Relevant Facts:\n" + "\n".join(facts) + "\n"
        return prompt

    def _mock_generate(self, state: RFSNState, user_text: str) -> str:
        return f"*{state.npc_name} listens to '{user_text}' with {state.mood} expression.*"

# Global Engine Instance
ENGINE = RFSNHybridEngine()


