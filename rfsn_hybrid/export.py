"""
Export utilities for conversation history and NPC data.

Export conversations to Markdown, JSON, or plain text for analysis,
backup, or integration with other tools.
"""
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from .types import RFSNState
from .storage import ConversationMemory, FactsStore, Turn


def export_conversation_markdown(
    memory: ConversationMemory,
    state: RFSNState,
    output_path: str,
    include_header: bool = True,
) -> str:
    """
    Export conversation to a Markdown file.
    
    Args:
        memory: Conversation memory to export
        state: Current NPC state for context
        output_path: Path to write markdown file
        include_header: Whether to include metadata header
        
    Returns:
        Path to the created file
    """
    lines = []
    
    if include_header:
        lines.extend([
            f"# Conversation with {state.npc_name}",
            "",
            "## NPC Info",
            f"- **Name**: {state.npc_name}",
            f"- **Role**: {state.role}",
            f"- **Affinity**: {state.affinity:.2f} ({state.attitude()})",
            f"- **Mood**: {state.mood}",
            f"- **Player**: {state.player_name}",
            "",
            f"*Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            "---",
            "",
            "## Conversation",
            "",
        ])
    
    for turn in memory.turns:
        speaker = state.player_name if turn.role == "user" else state.npc_name
        lines.append(f"**{speaker}**: {turn.content}")
        lines.append("")
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    return output_path


def export_conversation_json(
    memory: ConversationMemory,
    state: RFSNState,
    facts: Optional[FactsStore] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export conversation and state to JSON format.
    
    Args:
        memory: Conversation memory to export
        state: Current NPC state
        facts: Optional facts store
        output_path: Path to write JSON (None = just return dict)
        
    Returns:
        Dictionary with all exported data
    """
    data = {
        "exported_at": datetime.now().isoformat(),
        "npc": state.to_dict(),
        "conversation": [
            {
                "role": t.role,
                "content": t.content,
                "time": t.time,
            }
            for t in memory.turns
        ],
        "stats": {
            "total_turns": len(memory.turns),
            "user_messages": sum(1 for t in memory.turns if t.role == "user"),
            "assistant_messages": sum(1 for t in memory.turns if t.role == "assistant"),
        },
    }
    
    if facts:
        data["facts"] = [
            {
                "text": f.text,
                "tags": f.tags,
                "time": f.time,
                "salience": f.salience,
            }
            for f in facts.facts
        ]
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    return data


def export_conversation_text(
    memory: ConversationMemory,
    state: RFSNState,
    output_path: str,
) -> str:
    """
    Export conversation to plain text.
    
    Args:
        memory: Conversation memory
        state: NPC state for names
        output_path: Path to write text file
        
    Returns:
        Path to created file
    """
    lines = []
    
    for turn in memory.turns:
        speaker = state.player_name if turn.role == "user" else state.npc_name
        lines.append(f"{speaker}: {turn.content}")
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    return output_path


def export_facts_json(
    facts: FactsStore,
    output_path: str,
) -> str:
    """
    Export facts to JSON.
    
    Args:
        facts: Facts store to export
        output_path: Path to write JSON
        
    Returns:
        Path to created file
    """
    data = {
        "exported_at": datetime.now().isoformat(),
        "total_facts": len(facts.facts),
        "facts": [
            {
                "text": f.text,
                "tags": f.tags,
                "time": f.time,
                "salience": f.salience,
            }
            for f in facts.facts
        ],
    }
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    return output_path


def generate_conversation_summary(
    memory: ConversationMemory,
    state: RFSNState,
) -> str:
    """
    Generate a brief summary of the conversation.
    
    Args:
        memory: Conversation memory
        state: NPC state
        
    Returns:
        Summary string
    """
    total = len(memory.turns)
    user_count = sum(1 for t in memory.turns if t.role == "user")
    
    if total == 0:
        return f"No conversation with {state.npc_name} yet."
    
    # Find first and last messages
    first = memory.turns[0] if memory.turns else None
    last = memory.turns[-1] if memory.turns else None
    
    summary_parts = [
        f"Conversation with {state.npc_name} ({state.role})",
        f"Total exchanges: {total // 2}",
        f"Current relationship: {state.attitude()}",
        f"NPC mood: {state.mood}",
    ]
    
    if first:
        summary_parts.append(f"Started with: \"{first.content[:50]}...\"")
    if last:
        summary_parts.append(f"Last message: \"{last.content[:50]}...\"")
    
    return "\n".join(summary_parts)


class ConversationExporter:
    """
    Convenience class for exporting NPC data.
    
    Example:
        >>> exporter = ConversationExporter(memory, state, facts)
        >>> exporter.to_markdown("./exports/lydia.md")
        >>> exporter.to_json("./exports/lydia.json")
    """
    
    def __init__(
        self,
        memory: ConversationMemory,
        state: RFSNState,
        facts: Optional[FactsStore] = None,
    ):
        self.memory = memory
        self.state = state
        self.facts = facts
    
    def to_markdown(self, path: str) -> str:
        """Export to Markdown."""
        return export_conversation_markdown(self.memory, self.state, path)
    
    def to_json(self, path: str) -> str:
        """Export to JSON."""
        export_conversation_json(self.memory, self.state, self.facts, path)
        return path
    
    def to_text(self, path: str) -> str:
        """Export to plain text."""
        return export_conversation_text(self.memory, self.state, path)
    
    def summary(self) -> str:
        """Get conversation summary."""
        return generate_conversation_summary(self.memory, self.state)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get full export as dictionary."""
        return export_conversation_json(self.memory, self.state, self.facts)
