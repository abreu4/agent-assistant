# Agent Assistant

A powerful hybrid local+remote AI assistant with dual interfaces (CLI + GUI), intelligent model routing, and multi-provider support. Get instant AI assistance through a hotkey-triggered popup or interactive CLI.

## 🌟 Key Features

### Multiple Interfaces
- **CLI Mode**: Interactive command-line interface with streaming output
- **GUI Mode**: Hotkey-triggered popup (`Ctrl+Alt+Space`) for quick queries
- **Graceful Fallback**: Automatically falls back to CLI if hotkey setup fails

### Hybrid LLM Architecture
- **Local Models** (via Ollama): Privacy-focused, free, fast
  - Random selection from 6 general-purpose models
  - Llama 3.1, Llama 3.2, Mistral, Phi-3, Gemma 2, Qwen 2.5
- **Remote Models**: Access to 22+ models across 6 providers
  - OpenRouter (10+ free models)
  - OpenAI (GPT-4, GPT-4o, GPT-3.5)
  - Anthropic (Claude 3.5)
  - Google AI (Gemini)
  - Groq (ultra-fast inference)
  - Moonshot AI (Kimi K2)
- **Smart Routing**: Auto-routes based on complexity (simple → local, complex → remote)
- **Multi-Model Retry**: Tries 3 different remote models before falling back to local
- **Sticky Model**: Remembers last successful model for consistent performance

### Model Management
- **Random Selection**: Different local model for each query (optional)
- **Model Forcing**: `local` / `remote` / `auto` commands
- **Model Switching**: `switch <number>` to change remote model
- **Live Status**: `models`, `current`, `sticky` commands
- **Reset Preferences**: `reset-sticky` to clear model preferences

### Agent Capabilities
- File operations (read, write, search)
- Web search (DuckDuckGo or Tavily)
- Code execution (Docker sandbox)
- Intelligent routing and retry logic
- Cost tracking and budget limits

### Developer Experience
- **Streaming Output**: Word-by-word display like Claude
- **Loading Spinners**: Visual feedback during processing
- **Clean Logging**: Debug flag to reduce verbosity
- **Signal Handling**: Ctrl+C, Ctrl+Z, Ctrl+D for clean shutdown
- **Model Attribution**: See which model answered each query

## Architecture

```
┌─────────────────────────────────────────┐
│         User presses Ctrl+Alt+Space     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│           Popup GUI Window              │
│        "What can I help with?"          │
└────────────────┬────────────────────────┘
                 │ Query submitted
                 ▼
┌─────────────────────────────────────────┐
│          Task Queue                     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    LangGraph Workflow (Agent)           │
│  ┌────────────────────────────────────┐ │
│  │  1. Classify (using local 3B)      │ │
│  │     → Simple/Medium/Complex/Code   │ │
│  └────────────┬───────────────────────┘ │
│               │                          │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  2. Route                          │ │
│  │     → Local: Simple, Medium tasks  │ │
│  │     → Remote: Complex, Tool-heavy  │ │
│  └────────────┬───────────────────────┘ │
│               │                          │
│               ▼                          │
│  ┌─────────────────┬──────────────────┐ │
│  │  Ollama (Local) │ Kimi K2 (Remote) │ │
│  │  Llama 3.1 8B   │  via OpenRouter  │ │
│  └─────────────────┴──────────────────┘ │
│               │                          │
│               ▼                          │
│  ┌────────────────────────────────────┐ │
│  │  3. Tools (if needed)              │ │
│  │     • File ops                     │ │
│  │     • Web search                   │ │
│  │     • Code execution               │ │
│  └────────────────────────────────────┘ │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      Result Display Window              │
└─────────────────────────────────────────┘
```

## Prerequisites

- **Python**: 3.11+ (3.10 may work)
- **Ollama**: For local LLM inference
- **Docker**: For code execution sandbox (optional)
- **RAM**: 16GB+ recommended (8GB minimum for quantized models)
- **OS**: Linux (tested on WSL2, should work on native Linux)

## Installation

### 1. Install System Dependencies

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull local models
ollama pull llama3.1:8b        # Main local model (7GB)
ollama pull llama3.2:3b        # Fast classifier (2GB)
ollama pull mistral:7b         # Fallback (4GB)

# Verify Ollama is running
ollama list
```

### 2. Get API Keys (Optional but Recommended)

The service works with **local models only** (no API keys needed), but remote models provide better quality for complex queries.

**Recommended: OpenRouter (Easiest)**
1. Sign up at https://openrouter.ai
2. Get free credits ($5-10 to start)
3. Access to 10+ free models instantly

**Additional Providers (All Optional):**

| Provider | Sign Up | Benefits |
|----------|---------|----------|
| **Anthropic** | https://console.anthropic.com | Claude 3.5 - Best reasoning |
| **Google AI** | https://aistudio.google.com | Gemini - Free tier, 1M context |
| **Groq** | https://console.groq.com | Ultra-fast inference, free tier |
| **Moonshot AI** | https://platform.moonshot.cn | Kimi K2 - Long context |

**Note**: You only need ONE API key to get started (OpenRouter recommended). The service gracefully falls back to local models if no API keys are available.

### 3. Setup Project

```bash
# Clone or navigate to project directory
cd /home/tiago/projects/agent_assistant

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env

# Edit .env and add your API key
nano .env
# Add: OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 4. Configure Application

Edit `config/config.yaml` if needed:
- Hotkey combination (default: `ctrl+alt+space`)
- Model settings
- Tool preferences
- Workspace directory

### 5. Create Agent Workspace

```bash
# Create workspace directory (if different from default)
mkdir -p /home/tiago/agent_workspace
```

## 🚀 Quick Start

### 1. Run the Service

```bash
# Activate virtual environment
source venv/bin/activate

# Run the service
python3 run_service.py
```

### 2. Use CLI Mode

The service starts in CLI mode (no root required):

```
============================================================
🤖 Agent Assistant - Interactive CLI
============================================================
💬 Type your message, or use commands:
   • models - List all available models
   • switch <number> - Switch remote model
   • local / remote / auto - Force model tier
   • sticky - Show sticky model status
   • reset-sticky - Reset model preferences
   • current - Show current settings
   • exit / quit / q - Exit
============================================================

❯
```

**Try these commands:**

```bash
# Ask a question (uses local by default)
❯ What is Python?

# Ask for code
❯ Write a binary search function

# List all models
❯ models

# Allow auto routing
❯ auto
❯ Explain quantum computing in detail

# Check sticky models
❯ sticky

# Exit
❯ exit
```

### 3. CLI Features

- **Streaming Output**: Responses appear word-by-word like Claude
- **Loading Spinner**: Shows processing status
- **Model Attribution**: See which model answered: `🤖 Response (model: local (llama3.1:8b))`
- **Clean Shutdown**: Ctrl+C, Ctrl+Z, or Ctrl+D to exit gracefully

### 4. GUI Mode (Optional)

If you have root access and want hotkey support:

```bash
# Grant keyboard permissions
sudo setcap cap_net_admin+ep $(which python3)

# Run service (will enable hotkey)
python3 run_service.py

# Press Ctrl+Alt+Space to trigger popup
```

## 📖 Usage Guide

### CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `models` | List all available models | Shows local + remote |
| `switch <N>` | Switch to remote model N | `switch 5` |
| `current` | Show current remote model | |
| `sticky` | Show sticky model status | Displays locked models |
| `reset-sticky` | Reset model preferences | Clear sticky models |
| `local` | Force local model tier | Uses Ollama models |
| `remote` | Force remote model tier | Uses API models |
| `auto` | Re-enable auto routing | Default behavior |
| `exit`, `quit`, `q` | Exit CLI | |
| `Ctrl+C`, `Ctrl+Z` | Stop service | With goodbye message |
| `Ctrl+D` | Exit CLI mode | |

### Example Session

```bash
❯ python3 run_service.py

❯ Write a Python function to sort a list
🎲 Switched to local model: llama3.1:8b

============================================================
🤖 Response (model: local (llama3.1:8b))
============================================================
Here's a Python function using the built-in sorted() function:

def sort_list(items):
    """Sort a list in ascending order."""
    return sorted(items)

# Example usage:
numbers = [64, 34, 25, 12, 22, 11, 90]
sorted_numbers = sort_list(numbers)
print(sorted_numbers)  # [11, 12, 22, 25, 34, 64, 90]
============================================================

❯ sticky
📌 Model Lock Status
  💻 Local : ✓ llama3.1:8b
  🌐 Remote: ✓ mistralai/mistral-small-3.1-24b-instruct:free

❯ What is machine learning?

============================================================
🤖 Response (model: local (llama3.1:8b))
============================================================
Machine learning is a subset of artificial intelligence...
============================================================

❯ exit
👋 Thanks for using Agent Assistant!
```

### Installing as Systemd Service

```bash
# Grant keyboard access permissions (required for hotkey)
sudo setcap cap_net_admin+ep $(which python3)

# Update paths in service file if needed
nano config/agent_assistant.service

# Copy service file
sudo cp config/agent_assistant.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable agent_assistant

# Start service
sudo systemctl start agent_assistant

# Check status
sudo systemctl status agent_assistant
```

### Managing Service

```bash
# Start
sudo systemctl start agent_assistant

# Stop
sudo systemctl stop agent_assistant

# Restart
sudo systemctl restart agent_assistant

# Status
sudo systemctl status agent_assistant

# View logs (follow)
journalctl -u agent_assistant -f

# View recent logs
journalctl -u agent_assistant -n 100
```

## Configuration

### Environment Variables (.env)

```bash
# Remote Model Providers (all optional, pick one or more)
OPENROUTER_API_KEY=sk-or-v1-...    # Recommended
ANTHROPIC_API_KEY=sk-ant-...        # Optional
GOOGLE_API_KEY=...                  # Optional
GROQ_API_KEY=gsk_...                # Optional
MOONSHOT_API_KEY=sk-...             # Optional

# Tools (optional)
TAVILY_API_KEY=tvly-...  # For premium web search

# Settings
MONTHLY_BUDGET=50        # USD limit for remote models
LOG_LEVEL=INFO          # INFO or DEBUG
```

**Graceful Degradation**: Missing API keys won't crash the service. It will:
1. Try the model's native provider
2. Fall back to OpenRouter if available
3. Fall back to local models
4. Log warnings but continue working

### Application Config (config/config.yaml)

Key settings:

```yaml
llm:
  routing:
    prefer_local: true          # Use local when possible
    cost_limit_monthly: 50      # Budget limit (USD)

hotkey:
  combination: "ctrl+alt+space" # Change hotkey

tools:
  code_execution:
    sandbox: "docker"             # docker, restricted, or disabled
    enabled: true
```

## How It Works

### Routing Logic

The agent automatically routes queries based on complexity:

| Complexity | Examples | Model Used (with auto routing) |
|------------|----------|------------|
| **Simple** | "Hello", "What is X?", definitions | Local (Llama 3.1 8B) |
| **Medium** | Explanations, summaries | Local (Llama 3.1 8B) |
| **Complex** | Deep analysis, reasoning, multi-step | Remote (if enabled) |
| **Tool-heavy** | Needs search, execution, files | Remote (better reliability) |

**Note**: Default configuration uses `force_model: local` to prioritize local models.

### Cost Optimization

- Simple queries: FREE (local)
- Medium queries: FREE (local)
- Complex queries: $0.60/M input, $2.50/M output tokens
- Estimated monthly cost: $20-30 for personal use

### Retry Logic

If local model fails:
1. Query is automatically escalated to remote
2. Up to 3 retry attempts
3. Graceful error handling

## Troubleshooting

### "Permission denied" when running service

```bash
# Grant keyboard access without sudo
sudo setcap cap_net_admin+ep $(which python3)

# If that doesn't work, run service with sudo (not recommended)
sudo python3 src/service.py
```

### Hotkey not working

1. Check if service is running: `sudo systemctl status agent_assistant`
2. Check keyboard permissions: `getcap $(which python3)`
3. Try different hotkey in config.yaml
4. Check logs: `journalctl -u agent_assistant -f`

### Ollama connection failed

```bash
# Check if Ollama is running
ollama list

# Start Ollama if needed
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

### Remote API not working

1. Check .env file has correct API key
2. Test API key:
```bash
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```
3. Check account has credits/balance

### GUI not appearing

1. Check DISPLAY environment variable:
```bash
echo $DISPLAY  # Should show :0 or similar
```

2. Update service file with correct DISPLAY and XAUTHORITY

3. For WSL2:
```bash
export DISPLAY=:0
export XAUTHORITY=/mnt/c/Users/YourName/.Xauthority
```

### Docker code execution not working

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Start Docker
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in

# Pull Python image
docker pull python:3.11-slim

# Test
docker run python:3.11-slim python -c "print('Hello')"
```

### High memory usage

Local models use significant RAM:
- Llama 3.1 8B: ~8GB
- Llama 3.2 3B: ~3GB
- Mistral 7B: ~7GB

Options:
1. Use only one local model
2. Use smaller models (disable fallback)
3. Increase swap space
4. Use remote-only mode (set `prefer_local: false`)

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# 1. Ensure Ollama is running on host
ollama serve

# 2. Copy environment file
cp .env.example .env

# 3. Add your API keys to .env (optional)
nano .env

# 4. Build and run
docker-compose up -d

# 5. Attach to CLI
docker attach agent-assistant

# 6. Or run interactively
docker-compose run --rm agent-assistant
```

### Run Tests in Docker

```bash
# Run all tests
docker-compose run --rm agent-assistant pytest tests/ -v

# With coverage
docker-compose run --rm agent-assistant pytest tests/ --cov=src
```

### Docker Benefits

- **No local Python setup** - Everything in container
- **Consistent environment** - Same setup everywhere
- **Easy CI/CD** - Run tests in containers
- **Isolated dependencies** - No conflicts with host

See [docs/DOCKER.md](docs/DOCKER.md) for complete Docker documentation.

## 📚 Documentation

All documentation is in the `docs/` folder:

| Document | Description |
|----------|-------------|
| [QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) | Quick command reference |
| [KEYBOARD_SHORTCUTS.md](docs/KEYBOARD_SHORTCUTS.md) | All keyboard shortcuts |
| [LOCAL_MODELS.md](docs/LOCAL_MODELS.md) | Local model management |
| [MODEL_SELECTION_GUIDE.md](docs/MODEL_SELECTION_GUIDE.md) | Model selection strategies |
| [RETRY_STRATEGY.md](docs/RETRY_STRATEGY.md) | Multi-model retry logic |
| [TESTING.md](docs/TESTING.md) | Testing guide |
| [DOCKER.md](docs/DOCKER.md) | Docker deployment guide |
| [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) | Detailed setup instructions |
| [CHANGELOG.md](docs/CHANGELOG.md) | Recent changes |

## Development

### Project Structure

```
agent_assistant/
├── src/
│   ├── agent/              # Agent core logic
│   │   ├── llm_system.py   # LLM management
│   │   ├── router.py       # Routing logic
│   │   ├── tools.py        # Agent tools
│   │   └── workflow.py     # LangGraph workflow
│   ├── gui/                # GUI components
│   │   ├── popup.py        # Popup window
│   │   ├── hotkey.py       # Hotkey listener
│   │   ├── loading.py      # Loading spinner
│   │   └── streaming.py    # Streaming display
│   ├── utils/              # Utilities
│   │   ├── config.py       # Config management
│   │   └── logging.py      # Logging setup
│   └── service.py          # Main service
├── config/                 # Configuration
│   ├── config.yaml         # App config
│   └── agent_assistant.service  # Systemd service
├── docs/                   # Documentation
│   ├── QUICK_REFERENCE.md
│   ├── DOCKER.md
│   ├── TESTING.md
│   └── ...
├── tests/                  # Tests
│   ├── test_agent.py
│   └── test_force_model.py
├── workspace/              # Agent workspace
├── run_service.py          # Entry point
├── Dockerfile              # Docker image
├── docker-compose.yml      # Docker Compose config
├── requirements.txt        # Python dependencies
└── .env.example            # Environment template
```

### Running Tests

```bash
# Install test dependencies (already in requirements.txt)
pip install pytest pytest-asyncio

# Run tests
pytest tests/

# With coverage
pytest --cov=src tests/
```

### Adding Custom Tools

Edit `src/agent/tools.py`:

```python
@tool
def my_custom_tool(input: str) -> str:
    """
    Description of what this tool does.

    Args:
        input: Input description

    Returns:
        Output description
    """
    # Your implementation
    return result

# Add to get_agent_tools()
tools.append(my_custom_tool)
```

## FAQ

**Q: Can I use a different local model?**

A: Yes! Edit `config/config.yaml` and modify the `available_models` list:
```yaml
llm:
  local:
    available_models:
    - id: qwen2.5:7b
      name: Qwen 2.5 7B
      # ... add your preferred model
```

**Q: Can I use a different remote model?**

A: Yes! OpenRouter supports many models:
```yaml
llm:
  remote:
    model: "anthropic/claude-3.5-sonnet"  # Or any OpenRouter model
```

**Q: How do I disable code execution?**

A: Edit `config/config.yaml`:
```yaml
tools:
  code_execution:
    enabled: false
```

**Q: How do I use remote models instead of local?**

A: Set `force_model: auto` or `force_model: remote` in `config/config.yaml`:
```yaml
llm:
  routing:
    force_model: auto  # or "remote" to always use API models
```

**Q: Can I change the hotkey?**

A: Yes! Edit `config/config.yaml`:
```yaml
hotkey:
  combination: "ctrl+shift+a"  # Any keyboard combination
```

**Q: Does this work on macOS/Windows?**

A: Partially. The core agent works, but:
- Systemd service (Linux only) → Use alternatives (launchd on macOS, Task Scheduler on Windows)
- Hotkey library may need adjustments for OS-specific APIs

**Q: What's the minimum hardware?**

A:
- CPU-only: 16GB RAM (can work with 8GB using smaller models)
- With GPU: 8GB RAM + 8GB VRAM for optimal performance
- Storage: ~20GB for models

**Q: Is my data private?**

A:
- Local model queries: 100% private (never leave your machine)
- Remote API queries: Sent to OpenRouter/Moonshot servers
- Agent workspace: Local files only
- For maximum privacy: Use `prefer_local: true` and limit remote API usage

## License

[Specify your license here]

## Credits

- **Kimi K2**: Moonshot AI (https://platform.moonshot.cn)
- **Ollama**: Ollama team (https://ollama.ai)
- **LangChain/LangGraph**: LangChain Inc.
- **OpenRouter**: OpenRouter (https://openrouter.ai)

## Support

For issues, questions, or contributions:
- GitHub Issues: [Your repo URL]
- Documentation: [Your docs URL]

---

**Happy agent-ing! 🤖**
