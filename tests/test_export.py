"""
Tests for the export utilities.
"""
import os
import json
import tempfile

import pytest

from rfsn_hybrid.export import (
    export_conversation_markdown,
    export_conversation_json,
    export_conversation_text,
    generate_conversation_summary,
    ConversationExporter,
)
from rfsn_hybrid.types import RFSNState
from rfsn_hybrid.storage import ConversationMemory, FactsStore


@pytest.fixture
def sample_state():
    """Create a sample NPC state."""
    return RFSNState(
        npc_name="Lydia",
        role="Housecarl",
        affinity=0.75,
        mood="Happy",
        player_name="Hero",
        player_playstyle="Combatant",
        recent_memory="We fought together",
    )


@pytest.fixture
def sample_conversation(tmp_path):
    """Create a sample conversation."""
    path = str(tmp_path / "convo.json")
    memory = ConversationMemory(path)
    memory.add("user", "Hello Lydia!")
    memory.add("assistant", "Greetings, my Thane.")
    memory.add("user", "How are you?")
    memory.add("assistant", "I am well, ready to serve.")
    return memory


class TestExportMarkdown:
    """Test Markdown export functionality."""
    
    def test_creates_file(self, sample_state, sample_conversation, tmp_path):
        """Should create a markdown file."""
        output = str(tmp_path / "export.md")
        
        result = export_conversation_markdown(
            sample_conversation, sample_state, output
        )
        
        assert os.path.exists(result)
    
    def test_contains_npc_info(self, sample_state, sample_conversation, tmp_path):
        """Markdown should contain NPC information."""
        output = str(tmp_path / "export.md")
        
        export_conversation_markdown(sample_conversation, sample_state, output)
        
        with open(output) as f:
            content = f.read()
        
        assert "Lydia" in content
        assert "Housecarl" in content
        assert "Happy" in content
    
    def test_contains_messages(self, sample_state, sample_conversation, tmp_path):
        """Markdown should contain conversation messages."""
        output = str(tmp_path / "export.md")
        
        export_conversation_markdown(sample_conversation, sample_state, output)
        
        with open(output) as f:
            content = f.read()
        
        assert "Hello Lydia!" in content
        assert "Greetings, my Thane" in content


class TestExportJson:
    """Test JSON export functionality."""
    
    def test_returns_dict(self, sample_state, sample_conversation):
        """Should return a dictionary."""
        result = export_conversation_json(
            sample_conversation, sample_state
        )
        
        assert isinstance(result, dict)
        assert "npc" in result
        assert "conversation" in result
    
    def test_creates_file(self, sample_state, sample_conversation, tmp_path):
        """Should create JSON file when path provided."""
        output = str(tmp_path / "export.json")
        
        export_conversation_json(
            sample_conversation, sample_state, output_path=output
        )
        
        assert os.path.exists(output)
        
        with open(output) as f:
            data = json.load(f)
        
        assert data["npc"]["npc_name"] == "Lydia"
    
    def test_includes_facts(self, sample_state, sample_conversation, tmp_path):
        """Should include facts when provided."""
        facts_path = str(tmp_path / "facts.json")
        facts = FactsStore(facts_path)
        facts.add_fact("Test fact", ["test"], 0.8)
        
        result = export_conversation_json(
            sample_conversation, sample_state, facts=facts
        )
        
        assert "facts" in result
        assert len(result["facts"]) == 1
    
    def test_stats_accurate(self, sample_state, sample_conversation):
        """Stats should accurately count messages."""
        result = export_conversation_json(
            sample_conversation, sample_state
        )
        
        assert result["stats"]["total_turns"] == 4
        assert result["stats"]["user_messages"] == 2
        assert result["stats"]["assistant_messages"] == 2


class TestExportText:
    """Test plain text export."""
    
    def test_creates_file(self, sample_state, sample_conversation, tmp_path):
        """Should create text file."""
        output = str(tmp_path / "export.txt")
        
        result = export_conversation_text(
            sample_conversation, sample_state, output
        )
        
        assert os.path.exists(result)
    
    def test_simple_format(self, sample_state, sample_conversation, tmp_path):
        """Text format should be simple speaker: message."""
        output = str(tmp_path / "export.txt")
        
        export_conversation_text(sample_conversation, sample_state, output)
        
        with open(output) as f:
            content = f.read()
        
        assert "Hero: Hello Lydia!" in content
        assert "Lydia: Greetings, my Thane." in content


class TestConversationSummary:
    """Test conversation summary generation."""
    
    def test_empty_conversation(self, sample_state, tmp_path):
        """Should handle empty conversation."""
        path = str(tmp_path / "empty.json")
        memory = ConversationMemory(path)
        
        summary = generate_conversation_summary(memory, sample_state)
        
        assert "No conversation" in summary
    
    def test_includes_key_info(self, sample_state, sample_conversation):
        """Summary should include key information."""
        summary = generate_conversation_summary(
            sample_conversation, sample_state
        )
        
        assert "Lydia" in summary
        assert "Housecarl" in summary


class TestConversationExporter:
    """Test the ConversationExporter class."""
    
    def test_to_markdown(self, sample_state, sample_conversation, tmp_path):
        """Should export to markdown."""
        exporter = ConversationExporter(sample_conversation, sample_state)
        path = str(tmp_path / "export.md")
        
        result = exporter.to_markdown(path)
        
        assert os.path.exists(result)
    
    def test_to_json(self, sample_state, sample_conversation, tmp_path):
        """Should export to JSON."""
        exporter = ConversationExporter(sample_conversation, sample_state)
        path = str(tmp_path / "export.json")
        
        result = exporter.to_json(path)
        
        assert os.path.exists(result)
    
    def test_to_dict(self, sample_state, sample_conversation):
        """Should return dictionary."""
        exporter = ConversationExporter(sample_conversation, sample_state)
        
        result = exporter.to_dict()
        
        assert isinstance(result, dict)
        assert "conversation" in result
    
    def test_summary(self, sample_state, sample_conversation):
        """Should generate summary."""
        exporter = ConversationExporter(sample_conversation, sample_state)
        
        summary = exporter.summary()
        
        assert isinstance(summary, str)
        assert len(summary) > 0
