"""
LLM-based intent classification for more accurate event parsing.

This module provides an alternative to the keyword-based parse_event() in
state_machine.py, using the already-loaded LLM to classify player intent.
Falls back to keyword-based classification if LLM classification fails.
"""
from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING
import logging

from .types import Event, EventType
from .state_machine import parse_event as keyword_parse_event

if TYPE_CHECKING:
    from llama_cpp import Llama

logger = logging.getLogger(__name__)


# Prompt template for intent classification
INTENT_CLASSIFICATION_PROMPT = """You are classifying player dialogue in a fantasy RPG.

Classify the player's statement into exactly ONE of these categories:
- GIFT: Player is giving something to the NPC
- PUNCH: Player physically attacks or strikes the NPC
- INSULT: Player verbally abuses or disrespects the NPC
- THREATEN: Player threatens harm or violence
- PRAISE: Player compliments, thanks, or shows gratitude
- HELP: Player requests or offers assistance
- THEFT: Player admits to or is caught stealing
- QUEST_COMPLETE: Player reports completing a quest or task
- TALK: General conversation (default if unsure)

Player said: "{text}"

Respond with ONLY the category name (e.g., "PRAISE" or "TALK"), nothing else.
Category:"""


# Mapping from classification output to Event properties
EVENT_CONFIG = {
    "GIFT": {"strength": 1.0, "tags": ["gift"]},
    "PUNCH": {"strength": 1.0, "tags": ["violence"]},
    "INSULT": {"strength": 1.0, "tags": ["insult"]},
    "THREATEN": {"strength": 1.2, "tags": ["threat"]},
    "PRAISE": {"strength": 0.8, "tags": ["praise"]},
    "HELP": {"strength": 0.7, "tags": ["assist"]},
    "THEFT": {"strength": 1.0, "tags": ["crime"]},
    "QUEST_COMPLETE": {"strength": 1.0, "tags": ["quest"]},
    "TALK": {"strength": 0.2, "tags": ["talk"]},
}

VALID_INTENTS = set(EVENT_CONFIG.keys())


def classify_intent_with_llm(
    llm: "Llama",
    text: str,
    max_tokens: int = 10,
    temperature: float = 0.1,
) -> Optional[str]:
    """
    Use the LLM to classify player intent.
    
    Args:
        llm: The loaded Llama model instance
        text: The player's input text
        max_tokens: Maximum tokens for the response
        temperature: Sampling temperature (low for deterministic)
        
    Returns:
        The classified intent string, or None if classification failed
    """
    prompt = INTENT_CLASSIFICATION_PROMPT.format(text=text)
    
    try:
        result = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["\n", ".", ","],
            echo=False,
        )
        
        response = result["choices"][0]["text"].strip().upper()
        
        # Clean up the response - extract just the intent word
        for intent in VALID_INTENTS:
            if intent in response:
                return intent
        
        logger.debug(f"LLM returned unrecognized intent: {response}")
        return None
        
    except Exception as e:
        logger.warning(f"LLM intent classification failed: {e}")
        return None


def classify_intent(
    text: str,
    llm: Optional["Llama"] = None,
    use_llm: bool = True,
) -> Event:
    """
    Classify player input into an Event, optionally using LLM.
    
    This function tries LLM-based classification first (if enabled and available),
    then falls back to keyword-based classification.
    
    Args:
        text: The player's input text
        llm: Optional Llama model for LLM-based classification
        use_llm: Whether to attempt LLM classification
        
    Returns:
        An Event with the classified type, strength, and tags
    """
    intent = None
    
    # Try LLM classification first
    if use_llm and llm is not None:
        intent = classify_intent_with_llm(llm, text)
        if intent:
            logger.debug(f"LLM classified '{text[:30]}...' as {intent}")
    
    # Fall back to keyword-based if LLM didn't classify
    if intent is None:
        event = keyword_parse_event(text)
        logger.debug(f"Keyword classified '{text[:30]}...' as {event.type}")
        return event
    
    # Build Event from LLM classification
    config = EVENT_CONFIG.get(intent, EVENT_CONFIG["TALK"])
    return Event(
        type=intent,  # type: ignore
        raw_text=text,
        strength=config["strength"],
        tags=config["tags"],
    )


class IntentClassifier:
    """
    Stateful intent classifier that manages LLM reference.
    
    This provides a cleaner interface for the CLI, encapsulating
    the classification logic and LLM reference.
    
    Example:
        >>> classifier = IntentClassifier(llm, use_llm=True)
        >>> event = classifier.classify("Thanks for your help!")
        >>> print(event.type)  # "PRAISE"
    """
    
    def __init__(
        self,
        llm: Optional["Llama"] = None,
        use_llm: bool = True,
    ):
        """
        Initialize the classifier.
        
        Args:
            llm: The Llama model instance (can be set later)
            use_llm: Whether to use LLM-based classification
        """
        self.llm = llm
        self.use_llm = use_llm
        self._classification_count = 0
        self._llm_success_count = 0
    
    def classify(self, text: str) -> Event:
        """
        Classify the input text into an Event.
        
        Args:
            text: The player's input text
            
        Returns:
            An Event with the classified type
        """
        self._classification_count += 1
        
        if self.use_llm and self.llm is not None:
            intent = classify_intent_with_llm(self.llm, text)
            if intent:
                self._llm_success_count += 1
                config = EVENT_CONFIG.get(intent, EVENT_CONFIG["TALK"])
                return Event(
                    type=intent,  # type: ignore
                    raw_text=text,
                    strength=config["strength"],
                    tags=config["tags"],
                )
        
        # Fallback to keyword-based
        return keyword_parse_event(text)
    
    @property
    def stats(self) -> dict:
        """Get classification statistics."""
        return {
            "total": self._classification_count,
            "llm_successes": self._llm_success_count,
            "llm_rate": (
                self._llm_success_count / self._classification_count
                if self._classification_count > 0 else 0.0
            ),
        }
