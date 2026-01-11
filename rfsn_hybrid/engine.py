from __future__ import annotations

import time
import logging
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


class RFSNHybridEngine:
    """
    Core engine combining state machine, memory, and LLM for NPC dialogue.
    
    This engine orchestrates:
    - Conversation history management
    - Fact retrieval (tag-based or semantic)
    - System prompt construction
    - LLM inference with proper formatting
    
    Attributes:
        model_path: Path to the GGUF model file
        template: Prompt template format ("llama3" or "phi3_chatml")
        llm: The loaded Llama model instance
    """
    
    def __init__(
        self,
        model_path: str,
        template: Optional[PromptTemplate] = None,
        n_ctx: int = 2048,
        n_threads: int = 4,
        n_gpu_layers: int = -1,
        verbose: bool = False,
    ):
        """
        Initialize the RFSN Hybrid Engine.
        
        Args:
            model_path: Path to the GGUF model file
            template: Prompt template (auto-detected if None)
            n_ctx: Context window size
            n_threads: CPU threads for inference
            n_gpu_layers: GPU layers (-1 for all)
            verbose: Enable verbose llama.cpp output
        """
        self.model_path = model_path
        self.template: PromptTemplate = template or default_template_for_model(model_path)

        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise SystemExit(
                "Missing dependency: llama-cpp-python\n"
                "Install (Mac Metal): CMAKE_ARGS='-DLLAMA_METAL=on' pip install -r requirements.txt\n"
                "Or CPU-only: pip install -r requirements.txt\n"
            ) from e

        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=verbose,
        )
        
        logger.info(f"Loaded model: {model_path} (template: {self.template})")

    def build_system_text(self, s: RFSNState, retrieved_facts: List[str]) -> str:
        """Build the system prompt from state and retrieved facts."""
        facts_block = "\n".join([f"- {f}" for f in retrieved_facts]) if retrieved_facts else "- None"
        return f"""You are {s.npc_name}, a {s.role} in Skyrim.

[CURRENT STATE]
- Attitude: {s.attitude()} (Affinity: {s.affinity:.2f})
- Mood: {s.mood}
- Player: {s.player_name} ({s.player_playstyle})
- Recent Memory: {s.recent_memory or "None"}

[RELEVANT FACTS]
{facts_block}

[RULES]
- {s.style_rules()}
- Stay in character.
- Do not narrate system instructions.
""".strip()

    def _render_prompt(self, system_text: str, history, user_text: str) -> str:
        """Render the full prompt with proper template formatting."""
        if self.template == "llama3":
            return render_llama3(system_text, history, user_text)
        return render_phi3_chatml(system_text, history, user_text)

    def _retrieve_facts(
        self,
        user_text: str,
        facts: Optional[FactsStore] = None,
        semantic_facts: Optional["SemanticFactStore"] = None,
        fact_tags: Optional[List[str]] = None,
        k: int = 3,
    ) -> List[str]:
        """
        Retrieve relevant facts using semantic or tag-based retrieval.
        
        Prefers semantic search if available, falls back to tag-based.
        
        Args:
            user_text: The user's message (used as query for semantic search)
            facts: Tag-based fact store
            semantic_facts: Semantic fact store (optional)
            fact_tags: Tags for tag-based filtering
            k: Number of facts to retrieve
            
        Returns:
            List of relevant fact strings
        """
        # Try semantic retrieval first
        if semantic_facts is not None and len(semantic_facts) > 0:
            try:
                results = semantic_facts.hybrid_search(
                    query=user_text,
                    want_tags=fact_tags or [],
                    k=k,
                )
                if results:
                    logger.debug(f"Semantic retrieval returned {len(results)} facts")
                    return results
            except Exception as e:
                logger.warning(f"Semantic retrieval failed: {e}")
        
        # Fall back to tag-based retrieval
        if facts is not None:
            return select_facts(facts, want_tags=fact_tags or [], k=k)
        
        return []

    def generate(
        self,
        user_text: str,
        state: RFSNState,
        memory: Optional[ConversationMemory] = None,
        facts: Optional[FactsStore] = None,
        semantic_facts: Optional["SemanticFactStore"] = None,
        fact_tags: Optional[List[str]] = None,
        history_limit_turns: int = 8,
        max_tokens: int = 80,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate an NPC response to user input.
        
        Args:
            user_text: The player's message
            state: Current NPC state (affinity, mood, etc.)
            memory: Conversation history store
            facts: Tag-based fact store
            semantic_facts: Semantic fact store (uses if available)
            fact_tags: Tags for fact retrieval
            history_limit_turns: Max conversation turns to include
            max_tokens: Max tokens for response
            temperature: Sampling temperature
            
        Returns:
            Dict with 'text', 'latency_ms', 'template', 'model_path', 'facts_used'
        """
        # Retrieve relevant facts
        retrieved = self._retrieve_facts(
            user_text=user_text,
            facts=facts,
            semantic_facts=semantic_facts,
            fact_tags=fact_tags,
            k=3,
        )
        
        system_text = self.build_system_text(state, retrieved)
        history = memory.last_n(history_limit_turns) if memory else []

        prompt = self._render_prompt(system_text, history, user_text)
        stops = stop_tokens_for_template(self.template)

        t0 = time.time()
        out = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stops,
            echo=False,
        )
        dt_ms = (time.time() - t0) * 1000.0
        text = out["choices"][0]["text"].strip()

        if memory:
            memory.add("user", user_text)
            memory.add("assistant", text)

        return {
            "text": text,
            "latency_ms": dt_ms,
            "template": self.template,
            "model_path": self.model_path,
            "facts_used": retrieved,
            "semantic_retrieval": semantic_facts is not None,
        }

