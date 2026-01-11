# RFSN Hybrid Engine v0.5.2

A production-hardened NPC dialogue engine combining a **finite-state affinity system** with **local LLM inference** via `llama-cpp-python`. Designed for Skyrim mods (Mantella-compatible) but usable for any stateful NPC conversation system.

## What's New

### v0.5.2
- **Input Validation**: Sanitization and validation for all inputs
- **Health Checks**: Component monitoring and dependency verification
- **Optimized Reducer**: O(1) dispatch table with snapshot caching
- **LRU Embedding Cache**: Cached query embeddings for semantic search
- **160 Tests** (up from 83)

### v0.5.0 - Production Hardening
- Version compatibility enforcement
- Event reducer with single-writer state
- FRAME protocol for transactional streaming
- Backpressure handling with bounded queues
- Lifecycle management with graceful shutdown
- Build manifests with SHA256 verification

### v0.4.x
- REST API, Config System, Export Utilities, Semantic Memory

## Features

| Category | Features |
|----------|----------|
| **State** | Affinity (-1 to 1), mood tracking, event transitions |
| **Memory** | Persistent history, facts, semantic search (FAISS) |
| **Inference** | Local GGUF models, Llama 3 / Phi-3 templates |
| **Integration** | REST API, NPC presets, conversation export |
| **Production** | Validation, health checks, structured logging, metrics |
| **Safety** | Transaction support, backpressure, graceful shutdown |

## Installation

```bash
# Standard
pip install .

# With semantic memory + API + dev tools
pip install ".[all]"

# Mac Metal acceleration
CMAKE_ARGS='-DLLAMA_METAL=on' pip install .
```

## Quick Start

### CLI Mode
```bash
python -m rfsn_hybrid.cli --model "/path/to/model.gguf"
```

### API Server
```bash
python -m rfsn_hybrid.api --model "/path/to/model.gguf"
# Docs at http://localhost:8000/docs
```

### Health Check
```python
from rfsn_hybrid.health import run_health_checks

health = run_health_checks()
print(f"Healthy: {health.healthy}")
for check in health.checks:
    print(f"  {check.name}: {check.message}")
```

### Input Validation
```python
from rfsn_hybrid.validation import validate_config, sanitize_text

config = {"npc_name": "Lydia", "role": "Housecarl"}
result = validate_config(config)
if not result.is_valid:
    print(result.errors)

user_input = sanitize_text("  Hello world  \x00")  # "Hello world"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/presets` | GET | List NPC presets |
| `/npc/{id}/chat` | POST | Chat with NPC |
| `/npc/{id}/status` | GET | Get NPC state |
| `/npc/{id}/reset` | POST | Reset NPC |

## NPC Presets

| Preset | Name | Role |
|--------|------|------|
| `lydia` | Lydia | Housecarl |
| `merchant` | Belethor | Merchant |
| `guard` | Whiterun Guard | Guard |
| `innkeeper` | Hulda | Innkeeper |
| `mage` | Farengar | Court Wizard |

## Architecture

```
rfsn_hybrid/
├── engine.py          # Core LLM orchestration
├── types.py           # RFSNState, Event dataclasses
├── state_machine.py   # Affinity transitions
├── storage.py         # Persistence layer
├── semantic_memory.py # FAISS vector search
├── api.py             # FastAPI server
├── cli.py             # Interactive CLI
├── validation.py      # Input validation
├── health.py          # Health checks
├── lifecycle.py       # Startup/shutdown management
├── metrics.py         # Performance metrics
├── logging_config.py  # Structured logging
├── core/
│   ├── state/         # Event reducer + store
│   └── queues.py      # Backpressure handling
└── streaming/         # FRAME protocol
```

## Tests

```bash
pytest -v                           # Run all tests
pytest --cov=rfsn_hybrid            # With coverage
# 160 tests passing
```

## Dependencies

**Required:** `llama-cpp-python>=0.2.90`

**Optional:**
- `[semantic]`: faiss-cpu, sentence-transformers
- `[api]`: fastapi, uvicorn
- `[dev]`: pytest

## License

MIT
