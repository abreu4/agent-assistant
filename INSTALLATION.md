# Installation Guide

## 📦 Installing Agent Assistant as a Python Package

Agent Assistant can be installed as a pip package, allowing you to use it in any repository you're working on.

### Prerequisites

- Python 3.10 or higher
- Ollama installed and running (for local models)
- Git

### Installation Methods

#### 1. **Editable Installation (Recommended for Development)**

This allows you to modify the code and see changes immediately:

```bash
# Clone the repository
git clone <repository-url> agent-assistant
cd agent-assistant

# Install in editable mode
pip install -e .

# Or with optional dependencies
pip install -e ".[dev]"              # Include development tools
pip install -e ".[anthropic]"        # Include Anthropic/Claude support
pip install -e ".[google]"           # Include Google AI support
pip install -e ".[dev,anthropic,google]"  # All optional deps
```

#### 2. **Regular Installation**

For production use or when you don't need to modify the code:

```bash
pip install git+<repository-url>
```

#### 3. **From Local Directory**

If you have the source code locally:

```bash
cd /path/to/agent-assistant
pip install .
```

### Configuration

After installation, you need to set up your configuration:

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your API keys** (optional for remote models):
   ```bash
   # For OpenAI models
   OPENAI_API_KEY=sk-...

   # For other providers (optional)
   OPENROUTER_API_KEY=sk-or-...
   ANTHROPIC_API_KEY=sk-ant-...
   GOOGLE_API_KEY=...
   ```

3. **The configuration file is at:** `config/config.yaml`
   - This file contains model settings, tool configurations, etc.
   - You generally don't need to modify this unless you want custom settings

### Usage

#### As a CLI Tool

Once installed, you can run the assistant from **any directory**:

```bash
# Navigate to your project directory
cd /path/to/your/project

# Run the assistant
agent-assistant
```

**The assistant will:**
- Use the current working directory as its workspace
- Index all code files in the current directory
- Provide semantic search over your codebase
- Execute file operations in the current directory

#### Programmatic Usage

You can also import and use the agent in your Python code:

```python
from agent_assistant.agent.workflow import HybridAgent
import asyncio

async def main():
    agent = HybridAgent()
    await agent.initialize()

    result = await agent.run("Find all database models in this repo")
    print(agent.get_final_response(result))

asyncio.run(main())
```

### Verifying Installation

```bash
# Check if the command is available
which agent-assistant

# Show installed package info
pip show agent-assistant

# Test import
python -c "from agent_assistant.agent.workflow import HybridAgent; print('✓ Import successful')"
```

### Workspace Behavior

**Important:** The agent now works on the **current working directory** where you run it:

```bash
# Example 1: Work on a web app
cd ~/projects/my-webapp
agent-assistant
# → Agent indexes and works on my-webapp/

# Example 2: Work on a data science project
cd ~/projects/ml-analysis
agent-assistant
# → Agent indexes and works on ml-analysis/
```

**What gets indexed:**
- `.py`, `.js`, `.ts`, `.md`, `.json`, `.yaml`, `.txt`, etc.
- Excludes: `.git`, `node_modules`, `__pycache__`, `.venv`, etc.
- Index stored in `.agent_index/` (gitignored automatically)

### Uninstallation

```bash
pip uninstall agent-assistant
```

### Troubleshooting

#### Import Errors

If you get import errors, ensure you installed from the correct directory:
```bash
cd /path/to/agent-assistant
pip install -e .
```

#### Config File Not Found

The config file should be in the package. If missing, copy from the repository:
```bash
cp /path/to/agent-assistant/config/config.yaml ~/.config/agent-assistant/
```

#### Ollama Not Running

Ensure Ollama is running for local models:
```bash
ollama serve
```

#### Permission Errors

If you get permission errors during indexing, check that you have read/write access to the current directory.

### Development Workflow

For contributors and developers:

```bash
# 1. Clone and install in editable mode
git clone <repo-url>
cd agent-assistant
pip install -e ".[dev]"

# 2. Make changes to the code

# 3. Changes are immediately reflected (no reinstall needed)

# 4. Run tests
pytest

# 5. Format code
black src/
ruff check src/
```

### Next Steps

- Read the [Quick Reference](docs/QUICK_REFERENCE.md) for available commands
- Check [Model Selection Guide](docs/MODEL_SELECTION_GUIDE.md) for optimizing model choices
- See [README.md](README.md) for architecture and features
