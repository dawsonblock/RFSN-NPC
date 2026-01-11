# RFSN Hybrid Engine v0.4.1

A lightweight NPC dialogue engine combining a **finite-state affinity system** with **local LLM inference** via `llama-cpp-python`. Designed for Skyrim mods (Mantella-compatible) but usable for any stateful NPC conversation system.

## What's New

### v0.4.1
- **REST API**: FastAPI server for game integration
- **Config System**: YAML/JSON NPC presets with built-in characters
- **Export Utilities**: Export conversations to Markdown/JSON/text
- **More Tests**: 83 total tests (up from 41)

### v0.4.0
- **Semantic Memory**: FAISS-based vector search for intelligent fact retrieval
- **Smart Intent Classification**: LLM-based classification for accurate event parsing

## Features

- **State Machine**: Affinity (-1.0 to 1.0) and mood tracking with event-driven transitions
- **Persistent Memory**: Conversation history, facts, and NPC state survive restarts
- **Template Support**: Llama 3 and Phi-3 ChatML prompt formats with auto-detection
- **Semantic Memory**: Vector similarity search for fact retrieval
- **Smart Classification**: Use the LLM to classify player intent
- **REST API**: HTTP endpoints for game integration
- **NPC Presets**: Built-in personalities (Lydia, Belethor, Guards, etc.)
- **Dev Watch**: Hot-reload Python modules during development
- **Zero Cloud Dependencies**: Runs entirely local with GGUF models

## Installation

```bash
# Standard install
pip install .

# With semantic memory (FAISS + sentence-transformers)
pip install ".[semantic]"

# With REST API (FastAPI + uvicorn)
pip install ".[api]"

# Everything
pip install ".[all]"

# Mac Metal acceleration
CMAKE_ARGS='-DLLAMA_METAL=on' pip install .
```

## Quick Start

### CLI Mode
```bash
# Basic usage
python -m rfsn_hybrid.cli --model "/path/to/model.gguf"

# With semantic memory
python -m rfsn_hybrid.cli --model "/path/to/model.gguf" --semantic

# With smart classification
python -m rfsn_hybrid.cli --model "/path/to/model.gguf" --smart-classify
```

### API Server Mode
```bash
# Start API server (mock mode - no LLM required)
python -m rfsn_hybrid.api

# With LLM
python -m rfsn_hybrid.api --model "/path/to/model.gguf"

# API docs at http://localhost:8000/docs
```

### Demo Script
```bash
# Run interactive demo (no model required)
python demo.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/presets` | GET | List available NPC presets |
| `/npcs` | GET | List active NPC sessions |
| `/npc/{id}` | GET | Get NPC status |
| `/npc/{id}/chat` | POST | Send message, get response |
| `/npc/{id}/reset` | POST | Reset NPC state |
| `/npc/{id}/history` | GET | Get conversation history |

### Example API Usage
```bash
# Chat with Lydia
curl -X POST http://localhost:8000/npc/lydia/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Lydia!", "player_name": "Dragonborn"}'
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `quit` | Exit the CLI |
| `forget` | Wipe all conversation, facts, and state |
| `reload` | Hot-reload Python modules |
| `status` | Show NPC state and statistics |

## NPC Presets

Built-in character presets:

| Preset | Name | Role |
|--------|------|------|
| `lydia` | Lydia | Housecarl |
| `merchant` | Belethor | General Goods Merchant |
| `guard` | Whiterun Guard | City Guard |
| `innkeeper` | Hulda | Innkeeper |
| `mage` | Farengar | Court Wizard |

```python
from rfsn_hybrid.config import get_preset, ConfigManager

# Get built-in preset
lydia = get_preset("lydia")

# Or use ConfigManager for custom configs
manager = ConfigManager("./my_npcs")
my_npc = manager.get("custom_character")
```

## Export Conversations

```python
from rfsn_hybrid.export import ConversationExporter

exporter = ConversationExporter(memory, state, facts)

# Export to different formats
exporter.to_markdown("./exports/lydia.md")
exporter.to_json("./exports/lydia.json")
exporter.to_text("./exports/lydia.txt")

# Get summary
print(exporter.summary())
```

## Architecture

```
rfsn_hybrid/
├── types.py            # RFSNState, Event dataclasses
├── state_machine.py    # Affinity transitions, event parsing
├── storage.py          # Conversation + fact persistence
├── semantic_memory.py  # FAISS vector search
├── intent_classifier.py# LLM-based intent classification
├── config.py           # NPC presets and configuration
├── export.py           # Conversation export utilities
├── api.py              # FastAPI REST server
├── prompting.py        # LLM prompt templates
├── engine.py           # Core orchestrator
├── cli.py              # Interactive CLI
└── dev_watch.py        # File change detection
```

## Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=rfsn_hybrid --cov-report=term-missing

# Tests: 83 passing
```

## Dependencies

**Required:**
- `llama-cpp-python>=0.2.90`

**Optional:**
- `[semantic]`: faiss-cpu, sentence-transformers
- `[api]`: fastapi, uvicorn

## License

MIT
