<div align="center">

# 🎭 RFSN Hybrid Engine

**Production-Ready NPC Dialogue System with Local LLM Intelligence**

[![CI Status](https://github.com/dawsonblock/RFSN-NPC/workflows/CI/badge.svg)](https://github.com/dawsonblock/RFSN-NPC/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A production-hardened NPC dialogue engine combining a **finite-state affinity system** with **local LLM inference** via `llama-cpp-python`. Designed for Skyrim mods (Mantella-compatible) but usable for any stateful NPC conversation system.

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [API Reference](#-api-reference) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [What's New](#-whats-new)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Demo](#-demo)
- [API Reference](#-api-reference)
- [NPC Presets](#-npc-presets)
- [Architecture](#-architecture)
- [Testing](#-testing)
- [Performance](#-performance)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ What's New

<details>
<summary><strong>v0.5.2</strong> - Latest Release</summary>

- ✅ **Input Validation**: Sanitization and validation for all inputs
- 💚 **Health Checks**: Component monitoring and dependency verification
- ⚡ **Optimized Reducer**: O(1) dispatch table with snapshot caching
- 🧠 **LRU Embedding Cache**: Cached query embeddings for semantic search
- 🧪 **160 Tests** (up from 83)

</details>

<details>
<summary><strong>v0.5.0</strong> - Production Hardening</summary>

- Version compatibility enforcement
- Event reducer with single-writer state
- FRAME protocol for transactional streaming
- Backpressure handling with bounded queues
- Lifecycle management with graceful shutdown
- Build manifests with SHA256 verification

</details>

<details>
<summary><strong>v0.4.x</strong> - Feature Expansion</summary>

- REST API, Config System, Export Utilities, Semantic Memory

</details>

## 🚀 Features

<table>
<tr>
<td width="50%">

### 🎮 State Management
- **Affinity System**: Dynamic relationship tracking (-1 to 1)
- **Mood Tracking**: Emotional state transitions
- **Event-Driven**: Reactive state updates via events

### 💾 Memory & Context
- **Persistent History**: Conversation and state persistence
- **Semantic Search**: FAISS-powered fact retrieval
- **Context Window**: Smart context management for LLM

</td>
<td width="50%">

### 🤖 LLM Integration
- **Local Inference**: GGUF model support (Llama 3, Phi-3)
- **Template System**: Customizable prompt templates
- **No Cloud Required**: 100% local, private processing

### 🛡️ Production-Ready
- **Input Validation**: Sanitization & security checks
- **Health Monitoring**: Component health checks
- **Graceful Shutdown**: Proper lifecycle management
- **Metrics & Logging**: Structured observability

</td>
</tr>
</table>

## 📦 Installation

### Prerequisites
- Python 3.9 or higher
- 4GB+ RAM recommended for LLM inference
- GGUF model file (e.g., Llama 3, Phi-3)

### Basic Installation

```bash
# Clone the repository
git clone https://github.com/dawsonblock/RFSN-NPC.git
cd RFSN-NPC

# Install base package
pip install .
```

### Installation Options

<table>
<tr>
<td><strong>Option</strong></td>
<td><strong>Command</strong></td>
<td><strong>Use Case</strong></td>
</tr>
<tr>
<td>🎯 <strong>All Features</strong></td>
<td><code>pip install ".[all]"</code></td>
<td>Complete installation with API, semantic memory, and dev tools</td>
</tr>
<tr>
<td>🧠 <strong>Semantic Memory</strong></td>
<td><code>pip install ".[semantic]"</code></td>
<td>Adds FAISS vector search and sentence transformers</td>
</tr>
<tr>
<td>🌐 <strong>API Server</strong></td>
<td><code>pip install ".[api]"</code></td>
<td>Adds FastAPI and Uvicorn for REST API</td>
</tr>
<tr>
<td>🧪 <strong>Development</strong></td>
<td><code>pip install ".[dev]"</code></td>
<td>Adds pytest and development tools</td>
</tr>
</table>

### Platform-Specific Setup

<details>
<summary><strong>🍎 macOS with Metal (GPU Acceleration)</strong></summary>

```bash
CMAKE_ARGS='-DLLAMA_METAL=on' pip install .
```

</details>

<details>
<summary><strong>🐧 Linux with CUDA</strong></summary>

```bash
CMAKE_ARGS='-DLLAMA_CUDA=on' pip install .
```

</details>

<details>
<summary><strong>🪟 Windows</strong></summary>

```bash
# Ensure you have Visual Studio Build Tools installed
pip install .
```

</details>

## 🎯 Quick Start

### 1️⃣ Interactive CLI

Start an interactive conversation with an NPC:

```bash
python -m rfsn_hybrid.cli --model "/path/to/model.gguf"
```

**Example Session:**
```
🎭 NPC: Lydia the Housecarl
📊 Affinity: +0.00 (Neutral)

You: Here, take this gift
🎁 Event: GIFT (+0.2 affinity)
Lydia: "Thank you, my friend. This is most generous."

You: How are you feeling?
Lydia: "I am sworn to carry your burdens, and I do so gladly."
```

### 2️⃣ REST API Server

Launch the API server for integration with other applications:

```bash
python -m rfsn_hybrid.api --model "/path/to/model.gguf"
```

**Access the interactive docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

**Quick API Test:**
```bash
# Chat with Lydia
curl -X POST "http://localhost:8000/npc/lydia/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, Lydia!"}'

# Check NPC status
curl "http://localhost:8000/npc/lydia/status"
```

### 3️⃣ Python Integration

Use RFSN in your own Python projects:

```python
from rfsn_hybrid.engine import RFSNHybridEngine

# Initialize engine
engine = RFSNHybridEngine(model_path="/path/to/model.gguf")

# Generate response (engine manages NPC state internally)
payload = {
    "npc_id": "lydia",
    "text": "Hello, how are you?",
    # Optional fields (include if your integration needs them):
    "user_name": "Dragonborn",
}
response = engine.handle_message(**payload)

# Access response data
print(response["text"])  # NPC's response
print(f"Affinity: {response['state']['affinity']}")  # Updated state
print(f"Facts used: {len(response['facts_used'])}")  # Context facts
```

### 4️⃣ Advanced Features

<details>
<summary><strong>🧪 Health Checks</strong></summary>

```python
from rfsn_hybrid.health import run_health_checks

health = run_health_checks()
print(f"System Healthy: {health.healthy}")

for check in health.checks:
    status = "✅" if check.passed else "❌"
    print(f"{status} {check.name}: {check.message}")
```

</details>

<details>
<summary><strong>🛡️ Input Validation</strong></summary>

```python
from rfsn_hybrid.validation import validate_config, sanitize_text

# Validate configuration
config = {"npc_name": "Lydia", "role": "Housecarl"}
result = validate_config(config)

if not result.is_valid:
    print("Configuration errors:", result.errors)

# Sanitize user input
clean_text = sanitize_text("  Hello world  \x00")  # Returns: "Hello world"
```

</details>

## 🎬 Demo

Run the interactive demo to see all features in action without needing a model:

```bash
python demo.py
```

The demo showcases:
- ✨ State machine transitions (affinity, mood)
- 🧠 Semantic memory with FAISS search
- 💾 State persistence and recovery
- 🎯 Intent classification from player input

## 📚 API Reference

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/` | GET | Health check and system status | `curl http://localhost:8000/` |
| `/presets` | GET | List available NPC presets | `curl http://localhost:8000/presets` |
| `/npc/{id}/chat` | POST | Send message to NPC | `curl -X POST .../npc/lydia/chat -d '{"text":"Hi"}'` |
| `/npc/{id}/status` | GET | Get NPC state and affinity | `curl http://localhost:8000/npc/lydia/status` |
| `/npc/{id}/reset` | POST | Reset NPC to initial state | `curl -X POST .../npc/lydia/reset` |

**Full API Documentation:** Start the server and visit [http://localhost:8000/docs](http://localhost:8000/docs)

## 🎭 NPC Presets

Pre-configured NPCs ready to use out of the box:

| Preset ID | Character | Role | Starting Affinity | Personality Traits |
|-----------|-----------|------|-------------------|-------------------|
| `lydia` | Lydia | Housecarl | 0.6 (Neutral) | Loyal, dutiful, protective |
| `merchant` | Belethor | Merchant | 0.5 (Neutral) | Greedy, charming, opportunistic |
| `guard` | Whiterun Guard | City Guard | 0.4 (Wary) | Suspicious, professional, alert |
| `lydia` | Lydia | Housecarl | 0.6 | Loyal, dutiful, protective |
| `merchant` | Belethor | Merchant | 0.5 | Greedy, charming, opportunistic |
| `guard` | Whiterun Guard | City Guard | 0.4 | Suspicious, professional, alert |
| `innkeeper` | Hulda | Innkeeper | 0.5 | Welcoming, gossipy, hospitable |
| `mage` | Farengar | Court Wizard | 0.2 | Intellectual, impatient, scholarly |
# CLI with preset (Lydia as Housecarl)
python -m rfsn_hybrid.cli --npc Lydia --role Housecarl --model "/path/to/model.gguf"

# API endpoint
curl -X POST "http://localhost:8000/npc/merchant/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "What are you selling?"}'
```

## 🏗️ Architecture

```
rfsn_hybrid/
├── 🎮 Core Engine
│   ├── engine.py              # LLM orchestration and response generation
│   ├── types.py               # RFSNState, Event, Response dataclasses
│   └── state_machine.py       # Affinity transitions and event parsing
│
├── 💾 Storage & Memory
│   ├── storage.py             # Conversation history and state persistence
│   └── semantic_memory.py     # FAISS vector search for facts
│
├── 🌐 Interfaces
│   ├── api.py                 # FastAPI REST server
│   └── cli.py                 # Interactive command-line interface
│
├── 🛡️ Production Features
│   ├── validation.py          # Input sanitization and validation
│   ├── health.py              # Component health checks
│   ├── lifecycle.py           # Startup/shutdown management
│   ├── metrics.py             # Performance metrics collection
│   └── logging_config.py      # Structured logging configuration
│
├── ⚙️ Core Systems
│   ├── core/
│   │   ├── state/             # Event reducer with single-writer pattern
│   │   └── queues.py          # Backpressure-aware bounded queues
│   └── streaming/             # FRAME protocol for transactional streaming
│
└── 🧪 Tests (160+ tests)
    └── tests/                 # Comprehensive test suite
```

### Key Design Patterns

- **Event-Driven State**: All state changes flow through an event reducer
- **Single Writer**: State mutations are serialized to prevent race conditions
- **Backpressure Handling**: Bounded queues prevent memory exhaustion
- **Graceful Degradation**: System continues operating if optional features unavailable

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run with coverage report
pytest --cov=rfsn_hybrid --cov-report=term --cov-report=html

# Run specific test categories
pytest tests/test_engine.py -v          # Engine tests
pytest tests/test_state_machine.py -v   # State machine tests
pytest tests/test_validation.py -v      # Validation tests
```

**Test Coverage:** 160+ tests covering:
- ✅ Core engine and LLM integration
- ✅ State machine transitions
- ✅ Input validation and sanitization
- ✅ Health checks and monitoring
- ✅ API endpoints
- ✅ Semantic memory operations
- ✅ Event reducer and state management

## ⚡ Performance

### Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Event Dispatch | ~0.001ms | O(1) lookup with dispatch table |
| State Snapshot | ~0.01ms | Cached snapshots with LRU |
| Semantic Search (k=5) | ~10-50ms | FAISS with 10K facts |
| LLM Generation | ~100-5000ms | Depends on model size and hardware |

### Optimization Tips

```python
# 1. Enable LRU caching for embeddings
from rfsn_hybrid.semantic_memory import SemanticFactStore
store = SemanticFactStore("facts.json", cache_size=1000)

# 2. Use smaller, faster models for development
# Recommended: Phi-3-mini (3.8B) or Llama-3-8B-Instruct

# 3. Reduce context window for faster inference
engine = RFSNHybridEngine(model_path="model.gguf")
```

**System Requirements:**
- Minimum: 4GB RAM, 2 CPU cores
- Recommended: 8GB RAM, 4 CPU cores, GPU (Metal/CUDA)
- LLM Model: 2-13B parameters (GGUF format)

## 🔧 Troubleshooting

<details>
<summary><strong>❌ "No module named 'llama_cpp'"</strong></summary>

**Solution:** Install llama-cpp-python:
```bash
pip install llama-cpp-python>=0.2.90
```

For GPU acceleration, see [Platform-Specific Setup](#platform-specific-setup).

</details>

<details>
<summary><strong>❌ "FAISS not available" or semantic memory errors</strong></summary>

**Solution:** Install semantic dependencies:
```bash
pip install ".[semantic]"
```

</details>

<details>
<summary><strong>❌ Model loading errors or slow inference</strong></summary>

**Checklist:**
- ✅ Verify model file exists and is a valid GGUF format
- ✅ Ensure sufficient RAM (model size + 2GB minimum)
- ✅ Try a smaller model (e.g., Phi-3-mini instead of Llama-3-70B)
- ✅ Check GPU acceleration is properly configured

```python
# Test model loading
from llama_cpp import Llama
llm = Llama(model_path="/path/to/model.gguf", n_ctx=2048)
```

</details>

<details>
<summary><strong>🐛 Health checks failing</strong></summary>

**Solution:** Run diagnostics:
```python
from rfsn_hybrid.health import run_health_checks

health = run_health_checks()
for check in health.checks:
    if not check.passed:
        print(f"Failed: {check.name}")
        print(f"Reason: {check.message}")
        print(f"Fix: {check.details}")
```

</details>

<details>
<summary><strong>💡 Getting help</strong></summary>

- 📖 Check the [API documentation](http://localhost:8000/docs) (when server is running)
- 🐛 [Open an issue](https://github.com/dawsonblock/RFSN-NPC/issues) for bugs
- 💬 [Start a discussion](https://github.com/dawsonblock/RFSN-NPC/discussions) for questions
- 📧 Review existing issues and discussions

</details>

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone and install with dev dependencies
git clone https://github.com/dawsonblock/RFSN-NPC.git
cd RFSN-NPC
pip install -e ".[all]"

# Run tests
pytest -v

# Run linters
ruff check rfsn_hybrid/
mypy rfsn_hybrid/ --ignore-missing-imports
```

### Contribution Guidelines

1. 🔍 **Check existing issues** before starting work
2. 🌿 **Create a feature branch** from `main`
3. ✅ **Add tests** for new functionality
4. 📝 **Update documentation** as needed
5. ✨ **Ensure linters pass** (ruff, mypy)
6. 📬 **Submit a pull request** with clear description

### Areas for Contribution

- 🧪 Additional test coverage
- 📚 Documentation improvements
- 🎮 New NPC presets
- 🌐 Additional language model templates
- ⚡ Performance optimizations
- 🐛 Bug fixes

## 📄 Dependencies

### Core Requirements

**Required:**
- `llama-cpp-python>=0.2.90` - Local LLM inference with GGUF models
- `Python>=3.9` - Core language requirement

**Optional Feature Sets:**

| Feature | Package | Purpose |
|---------|---------|---------|
| `[semantic]` | - `faiss-cpu>=1.7.0`<br>- `sentence-transformers>=2.2.0` | Vector search and fact retrieval |
| `[api]` | - `fastapi>=0.100.0`<br>- `uvicorn>=0.20.0` | REST API server |
| `[dev]` | `pytest>=8.0.0` | Testing framework |
| `[all]` | All above | Complete feature set |

### Model Recommendations

**Recommended GGUF Models:**
- **Phi-3-mini-4k-instruct** (3.8B) - Fast, good for development
- **Llama 3 8B Instruct** (8B) - Balanced performance/quality
- **Llama 3 70B Instruct** (70B) - Highest quality, requires more resources

**Where to find models:**
- [Hugging Face](https://huggingface.co/models?library=gguf) - Search for GGUF models
- [TheBloke's Models](https://huggingface.co/TheBloke) - Quantized GGUF models

## 📜 License

MIT License – see the [MIT License text](https://opensource.org/licenses/MIT) for details.

**In short:** You can use this project for any purpose, commercial or non-commercial, as long as you include the original copyright and license notice.
MIT License – see the [`LICENSE`](LICENSE) file for details.
---

## 🌟 Acknowledgments

Built with:
- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Efficient LLM inference
- [FAISS](https://github.com/facebookresearch/faiss) - Vector similarity search
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [pytest](https://docs.pytest.org/) - Testing framework

Special thanks to the Skyrim modding community and [Mantella](https://github.com/art-from-the-machine/Mantella) project for inspiration.

---

<div align="center">

**⭐ Star this repo if you find it useful! ⭐**

[Report Bug](https://github.com/dawsonblock/RFSN-NPC/issues) • [Request Feature](https://github.com/dawsonblock/RFSN-NPC/issues) • [Discussions](https://github.com/dawsonblock/RFSN-NPC/discussions)

Made with ❤️ for the modding community

</div>
