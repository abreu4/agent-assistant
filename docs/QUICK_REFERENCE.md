# Quick Reference Guide

## CLI Commands

### Mode Switching

| Command | Description | Example |
|---------|-------------|---------|
| `mode default` | Switch to general-purpose models | Uses Llama, Mistral, Gemma, etc. |
| `mode code` | Switch to coding-focused models | Uses CodeLlama, DeepSeek Coder, etc. |
| `showmode` | Display current mode | Shows DEFAULT or CODE |

### Remote Model Management

| Command | Description |
|---------|-------------|
| `models` | List all available models (local + remote) |
| `switch <number>` | Switch to a different remote model |
| `current` | Show current remote model |

### Model Tier Forcing

| Command | Description |
|---------|-------------|
| `local` | Force next query to use local model |
| `remote` | Force next query to use remote model |
| `auto` | Enable automatic model selection |

### General

| Command | Description |
|---------|-------------|
| `exit`, `quit`, `q` | Stop the service |
| **Ctrl+C** or **Ctrl+Z** | Immediate shutdown |
| **Ctrl+D** | Exit CLI mode |

## Mode Switching Examples

### Switching to Code Mode

```
❯ mode code

⏳ Switching to code mode...
✓ Switched to CODE mode
Now using code-focused models (CodeLlama, DeepSeek Coder, etc.)

❯ Write a Python function for sorting

🎲 Switched to local model: codellama:7b

============================================================
🤖 Response (model: local (codellama:7b))
============================================================
def bubble_sort(arr):
    """Sort array using bubble sort algorithm."""
    n = len(arr)
    for i in range(n):
        ...
============================================================
```

### Switching to Default Mode

```
❯ mode default

⏳ Switching to default mode...
✓ Switched to DEFAULT mode
Now using general-purpose models (Llama, Mistral, etc.)

❯ What is quantum computing?

🎲 Switched to local model: llama3.1:8b

============================================================
🤖 Response (model: local (llama3.1:8b))
============================================================
Quantum computing is a revolutionary approach...
============================================================
```

### Checking Current Mode

```
❯ showmode

============================================================
🎯 Current Local Mode
============================================================
CODE mode
Using code-focused models
============================================================
```

## Model Selection Behavior

### With Random Selection Enabled

When `random_selection: true` in config:

- **Default Mode**: Randomly picks from 6 general models
- **Code Mode**: Randomly picks from 5 coding models
- **Changes**: Different model selected for each query
- **Indication**: Shows `🎲 Switched to local model: <name>`

### With Random Selection Disabled

When `random_selection: false` in config:

- **Always uses**: `llama3.1:8b` (default model)
- **Consistent**: Same model every time
- **No switching**: No random selection messages

## Configuration

Edit `config/config.yaml` to change settings:

```yaml
llm:
  local:
    random_selection: true    # Enable random model selection
    mode: default            # Current mode: "default" or "code"
```

## Visual Indicators

| Symbol | Meaning |
|--------|---------|
| 🎲 | Random model selected |
| ✓ [ACTIVE MODE] | This mode is currently active |
| ✓ [CURRENT] | This remote model is selected |
| 💻 | Local models |
| 🌐 | Remote models |
| 🤖 | Response from model |
| ⏳ | Processing/Switching |
| ⚠️ | Warning/Retry |
| 👋 | Goodbye message |

## Workflow Examples

### General Q&A Session

```
1. Start service: python3 run_service.py
2. Mode: default (already set)
3. Ask: "What is machine learning?"
4. Model: Random from Llama/Mistral/Gemma
5. Response: General explanation
```

### Coding Session

```
1. Switch: mode code
2. Ask: "Write a binary search function"
3. Model: Random from CodeLlama/DeepSeek Coder
4. Response: Code implementation
5. Ask: "Optimize this algorithm"
6. Model: Different coding model (random)
7. Response: Optimized code
```

### Mixed Session

```
1. Start in default mode
2. Ask general questions
3. Switch: mode code
4. Work on coding tasks
5. Switch: mode default
6. Back to general questions
```

## Tips

1. **Start Session**: Service defaults to `default` mode
2. **Switch Modes**: Use `mode code` when coding, `mode default` otherwise
3. **Check Mode**: Use `showmode` if you forget current mode
4. **See Models**: Use `models` to see what's in each mode
5. **Variety**: Random selection gives you different perspectives
6. **Consistency**: Disable random selection for predictable behavior

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Enter** | Submit query |
| **Ctrl+C** | Stop service |
| **Ctrl+Z** | Stop service |
| **Ctrl+D** | Exit CLI |
| **Ctrl+L** | Clear screen (terminal) |

## Model Attribution

Every response shows which model was used:

```
🤖 Response (model: local (codellama:7b))
```

This helps you:
- Track which model gave which response
- Compare model quality
- Identify patterns in model strengths

## Installation Check

Verify models are installed:

```bash
ollama list
```

Install missing models:

```bash
# Default models
ollama pull llama3.1:8b
ollama pull mistral:7b

# Code models
ollama pull codellama:7b
ollama pull deepseek-coder:6.7b
```
