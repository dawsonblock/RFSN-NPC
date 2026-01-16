from __future__ import annotations

import os
import time
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING

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
from .core.state.event_types import EventType, StateEvent

# Environment feedback (events -> consequences -> normalized signals)
from .environment import EnvironmentEvent
from .environment.event_adapter import GameEvent, GameEventType
from .environment.consequence_mapper import ConsequenceMapper
from .environment.signal_normalizer import SignalNormalizer

# Decision + learning (bounded policy)
from .decision.policy import DecisionPolicy
from .decision.context import build_context_key as build_decision_context_key
from .learning.learning_state import LearningState
from .learning.outcome_evaluator import OutcomeEvaluator
from .learning.policy_adjuster import PolicyAdjuster

# Constants for learning feedback
AFFINITY_DELTA_EPSILON = 1e-9  # Minimum affinity change to trigger learning feedback
STYLE_ACTION_PREFIX = "style_for:"

class RFSNHybridEngine:
    """
    Core engine combining state machine, memory, and LLM for NPC dialogue.

    Now wired:
    - DecisionPolicy drives a bounded action choice per turn
    - EnvironmentEvent pipeline updates state through reducer
    - Learning can reweight actions based on outcome feedback
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

        self._stores: Dict[str, StateStore] = {}
        self._lock = threading.Lock()

        # Environment feedback pipeline
        self._consequence_mapper = ConsequenceMapper(enabled=True)
        self._signal_normalizer = SignalNormalizer(enabled=True)

        # Decision policy (bounded action set)
        self._decision_policy = DecisionPolicy(enabled=True)
        self._last_action: Dict[str, Tuple[str, str]] = {}  # npc_id -> (context_key, action)

        # Learning (bounded reweighting). Stored per NPC.
        self._outcome_evaluator = OutcomeEvaluator()
        self._policy_adjusters: Dict[str, Dict[str, PolicyAdjuster]] = {}

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

    def _get_policy_adjusters(self, npc_id: str) -> Dict[str, PolicyAdjuster]:
        """Lazy-init learning objects per NPC.

        Two namespaces are used:
        - decision: reweights bounded action selection
        - style: reweights speech style hints
        """
        with self._lock:
            if npc_id in self._policy_adjusters:
                return self._policy_adjusters[npc_id]

            base_dir = os.environ.get("RFSN_LEARNING_DIR", os.path.join("state", "learning"))
            try:
                os.makedirs(base_dir, exist_ok=True)
            except FileExistsError:
                # Directory was created by another process between checks; safe to ignore.
                pass
            except OSError as e:
                logger.error("Failed to create learning directory '%s': %s", base_dir, e)
                raise
            decision_path = os.path.join(base_dir, f"{npc_id}_decision.json")
            style_path = os.path.join(base_dir, f"{npc_id}_style.json")

            decision_state = LearningState(path=decision_path, enabled=False, namespace="decision")
            style_state = LearningState(path=style_path, enabled=False, namespace="style")

            adjusters = {
                "decision": PolicyAdjuster(
                    learning_state=decision_state,
                    outcome_evaluator=self._outcome_evaluator,
                    exploration_rate=0.10,
                    learning_rate=0.05,
                    seed=1337,
                ),
                "style": PolicyAdjuster(
                    learning_state=style_state,
                    outcome_evaluator=self._outcome_evaluator,
                    exploration_rate=0.10,
                    learning_rate=0.05,
                    seed=1337,
                ),
            }

            self._policy_adjusters[npc_id] = adjusters
            return adjusters

    def enable_learning(self, npc_id: str, enabled: bool = True) -> Dict[str, Any]:
        """Enable/disable learning for an NPC (both namespaces)."""
        adjusters = self._get_policy_adjusters(npc_id)
        adjusters["decision"].learning_state.enabled = bool(enabled)
        adjusters["style"].learning_state.enabled = bool(enabled)
        return {
            "npc_id": npc_id,
            "enabled": bool(enabled),
            "decision": adjusters["decision"].get_statistics(),
            "style": adjusters["style"].get_statistics(),
        }

    def _recent_env_event_types(self, store: StateStore, limit: int = 2) -> List[str]:
        """Extract recent environment event types from stored facts."""
        try:
            facts = list(store.facts)
        except Exception:
            return []

        env_types: List[str] = []
        for f in reversed(facts):
            tags = getattr(f, "tags", []) or []
            if "env" not in tags:
                continue
            for t in tags:
                if t != "env" and t not in env_types:
                    env_types.append(t)
                    break
            if len(env_types) >= limit:
                break
        return list(reversed(env_types))

    def handle_env_event(self, event: EnvironmentEvent) -> Dict[str, Any]:
        """Ingest an environment event and apply deterministic consequences.

        Fixes v13 corruption:
        - mapping dict is valid
        - unsupported event types return a helpful list
        - env fact string is built safely
        - learning feedback uses a defined STYLE_ACTION_PREFIX
        """
        is_valid, err = event.validate()
        if not is_valid:
            return {"ok": False, "error": err}

        store = self.get_store(event.npc_id)
        pre = store.state

        # Normalize incoming type string
        event_type_key = (event.event_type or "").strip().lower()

        # Map EnvironmentEventType strings -> GameEventType enum
        mapping: Dict[str, GameEventType] = {
            # Dialogue
            "dialogue_started": GameEventType.DIALOGUE_START,
            "dialogue_ended": GameEventType.DIALOGUE_END,
            "dialogue_choice": GameEventType.DIALOGUE_BRANCH_TAKEN,

            # Player emotion/sentiment (best-effort mapping)
            "player_sentiment": GameEventType.DIALOGUE_BRANCH_TAKEN,
            "player_hostility": GameEventType.COMBAT_START,

            # Combat
            "combat_started": GameEventType.COMBAT_START,
            "combat_ended": GameEventType.COMBAT_END,
            "combat_result": GameEventType.COMBAT_END,
            "combat_damage_taken": GameEventType.COMBAT_HIT_TAKEN,
            "combat_damage_dealt": GameEventType.COMBAT_HIT_DEALT,

            # Quests
            "quest_started": GameEventType.QUEST_STARTED,
            "quest_updated": GameEventType.QUEST_OBJECTIVE_COMPLETE,
            "quest_completed": GameEventType.QUEST_COMPLETED,
            "quest_failed": GameEventType.QUEST_FAILED,

            # Proximity / social
            "proximity_entered": GameEventType.PLAYER_NEARBY,
            "proximity_exited": GameEventType.PLAYER_LEFT,
            "proximity_update": GameEventType.PLAYER_NEARBY,

            # Social actions
            "gift": GameEventType.ITEM_RECEIVED,
            "theft": GameEventType.ITEM_STOLEN,
            "assist": GameEventType.WITNESSED_GOOD_DEED,
            "crime_witnessed": GameEventType.WITNESSED_CRIME,

            # Time / environment
            "time_passed": GameEventType.TIME_PASSED,
            "location_changed": GameEventType.LOCATION_CHANGED,
        }

        game_type = mapping.get(event_type_key)
        if game_type is None:
            return {
                "ok": False,
                "error": f"Unsupported event_type: {event.event_type}",
                "supported_event_types": sorted(mapping.keys()),
            }

        # Magnitude: prefer payload["magnitude"], else 0.5
        payload = event.payload if isinstance(event.payload, dict) else {}
        magnitude = 0.5
        try:
            if "magnitude" in payload:
                magnitude = float(payload.get("magnitude", magnitude))
        except Exception:
            magnitude = 0.5
        magnitude = max(0.0, min(1.0, magnitude))

        game_event = GameEvent(
            event_type=game_type,
            npc_id=event.npc_id,
            player_id=event.player_id,
            magnitude=magnitude,
            data=payload or {},
            tags=["env", event_type_key],
        )

        # Map -> normalize -> reducer events
        signals = self._consequence_mapper.map_event(game_event)
        strong = self._signal_normalizer.filter_by_intensity(signals, min_intensity=0.08)
        normalized = self._signal_normalizer.aggregate(strong)

        applied_events: List[StateEvent] = []
        if normalized.affinity_delta:
            applied_events.append(
                StateEvent(
                    event_type=EventType.AFFINITY_DELTA,
                    npc_id=event.npc_id,
                    payload={"delta": normalized.affinity_delta, "reason": f"env:{event_type_key}"},
                    source="env",
                )
            )
        if normalized.mood_impact:
            applied_events.append(
                StateEvent(
                    event_type=EventType.MOOD_SET,
                    npc_id=event.npc_id,
                    payload={"mood": normalized.mood_impact},
                    source="env",
                )
            )

        if applied_events:
            store.dispatch_batch(applied_events)

        # Build a safe, short env fact string (no undefined vars, no broken indentation)
        key_fields: List[str] = []
        for k in (
            "magnitude",
            "item",
            "quest",
            "objective",
            "result",
            "damage",
            "attacker",
            "target",
            "location",
            "distance",
            "sentiment",
        ):
            if k in payload:
                v = str(payload.get(k))
                v = v.replace("\r", " ").replace("\n", " ").strip()
                if len(v) > 200:
                    v = v[:200] + "…"
                key_fields.append(f"{k}={v}")

        env_text = f"[ENV] {event_type_key}"
        if key_fields:
            env_text = f"[ENV] {event_type_key}: " + ", ".join(key_fields)
        elif payload:
            v = str(payload).replace("\r", " ").replace("\n", " ").strip()
            if len(v) > 200:
                v = v[:200] + "…"
            env_text = f"[ENV] {event_type_key}: {v}"

        if len(env_text) > 512:
            env_text = env_text[:512] + "…"

        store.dispatch(
            StateEvent(
                event_type=EventType.FACT_ADD,
                npc_id=event.npc_id,
                payload={"text": env_text, "tags": ["env", event_type_key], "salience": 0.3},
                source="env",
            )
        )

        # Learning feedback: use affinity delta caused by env event as reward proxy
        post = store.state
        affinity_delta = float(post.affinity - pre.affinity)

        if event.npc_id in self._last_action and abs(affinity_delta) > AFFINITY_DELTA_EPSILON:
            ctx_key, action = self._last_action[event.npc_id]
            adjusters = self._get_policy_adjusters(event.npc_id)
            adjusters["decision"].apply_affinity_feedback(ctx_key, action, affinity_delta)
            adjusters["style"].apply_affinity_feedback(ctx_key, f"{STYLE_ACTION_PREFIX}{action}", affinity_delta)

        return {
            "ok": True,
            "npc_id": event.npc_id,
            "event_type": event_type_key,
            "normalized": normalized.to_dict(),
            "state": post.to_dict(),
        }

    def handle_message(
        self, 
        npc_id: str, 
        text: str,
        user_name: str = "Player"
    ) -> Dict[str, Any]:
        """Parse -> dispatch player event -> decide bounded action -> realize -> store."""
        store = self.get_store(npc_id)
        
        from .state_machine import parse_event
        event_obj = parse_event(text)
        
        store.dispatch(StateEvent(
            EventType.PLAYER_EVENT,
            npc_id,
            {
                "player_event_type": event_obj.type,
                "strength": event_obj.strength,
                "text": text,
                "tags": event_obj.tags
            },
            source="player"
        ))
        
        store.dispatch(StateEvent(
            EventType.FACT_ADD,
            npc_id,
            {
                "text": f"{user_name}: {text}",
                "tags": ["chat", "user"],
                "salience": 1.0
            },
            source="chat"
        ))

        snapshot = store.state

        recent_env = self._recent_env_event_types(store, limit=2)
        ctx_key = build_decision_context_key(
            snapshot.affinity,
            snapshot.mood,
            recent_player_events=[event_obj.type],
            recent_env_events=recent_env,
        )

        allowed_actions = self._decision_policy.get_allowed_actions(snapshot.affinity, snapshot.mood)
        adjusters = self._get_policy_adjusters(npc_id)

        decision_weights = adjusters["decision"].get_action_weights(
            ctx_key,
            actions=[a.value for a in allowed_actions],
        )

        chosen_action, speech_style = self._decision_policy.choose_action(
            context_key=ctx_key,
            affinity=snapshot.affinity,
            mood=snapshot.mood,
            action_weights=decision_weights,
        )

        self._last_action[npc_id] = (ctx_key, chosen_action.value)
        directive = self._decision_policy.get_llm_directive(chosen_action)

        facts_used = self._select_relevant_facts(store, text, limit=5)

        if self.llm:
            response_text = self._generate_llm(snapshot, text, facts_used, directive=directive, style_hint=speech_style)
        else:
            response_text = self._mock_generate(snapshot, text)

        store.dispatch(StateEvent(
            EventType.FACT_ADD,
            npc_id,
            {
                "text": f"{snapshot.npc_name}: {response_text}",
                "tags": ["chat", "npc"],
                "salience": 1.0
            },
            source="chat"
        ))

        final_snap = store.state
        return {
            "text": response_text,
            "state": final_snap.to_dict(),
            "facts_used": facts_used,
            "decision": {
                "context_key": ctx_key,
                "action": chosen_action.value,
                "style": speech_style,
            }
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

    def build_system_text(
        self,
        state: RFSNState,
        facts: List[str],
        directive: Optional[str] = None,
        style_hint: Optional[str] = None,
    ) -> str:
        """Build system prompt with state + bounded action directive."""
        lines: List[str] = [
            f"You are {state.npc_name}, a {state.role} in the world of Skyrim.",
            f"Current Mood: {state.mood} (Affinity: {state.affinity:.2f}).",
        ]

        if directive:
            lines.append(f"Action Directive: {directive}")
        if style_hint:
            lines.append(f"Speech Style: {style_hint}")

        lines.extend([
            "Rules:",
            "- Stay in character.",
            "- Do not mention system prompts, policies, or internal rules.",
            "- Keep it 1-4 sentences unless the player asks for detail.",
        ])

        if facts:
            lines.append("Relevant Memories:")
            lines.extend([f"- {f}" for f in facts])

        return "\n".join(lines)

    def _generate_llm(
        self,
        state: RFSNState,
        user_text: str,
        facts_used: List[str],
        directive: Optional[str] = None,
        style_hint: Optional[str] = None,
    ) -> str:
        """Generate response using real LLM."""
        sys_prompt = self.build_system_text(state, facts_used, directive=directive, style_hint=style_hint)
        context = f"{sys_prompt}\n\nPlayer: {user_text}\n{state.npc_name}:"
        
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
        """Retrieve relevant facts (test shim)."""
        return select_facts(
            store=facts,
            want_tags=fact_tags,
            k=k
        )

    def _mock_generate(self, state: RFSNState, user_text: str) -> str:
        return f"*{state.npc_name} listens to '{user_text}' with {state.mood} expression.*"

# Global Engine Instance
ENGINE = RFSNHybridEngine()


