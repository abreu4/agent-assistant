# Keyboard Shortcuts & Controls

## CLI Mode Controls

### Stopping the Service

The Agent Assistant can be stopped using multiple keyboard shortcuts:

| Shortcut | Signal | Description |
|----------|--------|-------------|
| **Ctrl+C** | SIGINT | Interrupt - Immediately stops the service |
| **Ctrl+Z** | SIGTSTP | Suspend - Stops the service (same as Ctrl+C) |
| **Ctrl+D** | EOF | End of File - Gracefully exits CLI mode |

You can also type these commands:
- `exit`
- `quit`
- `q`

### During Prompt Input

When waiting for your input at the `❯` prompt:

| Action | Effect |
|--------|--------|
| **Enter** | Submit your query |
| **Ctrl+C** | Cancel current input, show interruption message |
| **Ctrl+D** | Exit the service |
| **Ctrl+Z** | Stop the service |

### During Processing

When you see the loading spinner (e.g., `⠋ Thinking...`):

| Action | Effect |
|--------|--------|
| **Ctrl+C** | Stops the service immediately |
| **Ctrl+Z** | Stops the service immediately |

**Note**: The current query processing cannot be interrupted - it will complete or timeout. The service stops after the current task.

## Graceful Shutdown

When you stop the service using any method, you'll see:

```
⚠️  Received SIGINT (Ctrl+C)

============================================================
👋 Thanks for using Agent Assistant!
============================================================
```

The service ensures:
1. Current task completes (or times out)
2. Task queue is cleaned up
3. All threads are properly stopped
4. Resources are released
5. Goodbye message is displayed

## CLI Commands

Available commands when the service is running:

| Command | Description |
|---------|-------------|
| `models` | List all available remote models |
| `switch <number>` | Switch to a different remote model |
| `current` | Show current remote model |
| `local` | Force local model for next query |
| `remote` | Force remote model for next query |
| `auto` | Enable automatic model selection |
| `exit`, `quit`, `q` | Stop the service |

## Tips

1. **Graceful Exit**: Use `exit` command for the cleanest shutdown
2. **Quick Exit**: Use Ctrl+C or Ctrl+Z when you need to stop immediately
3. **EOF Exit**: Ctrl+D is useful in scripted scenarios
4. **During Long Operations**: The service will complete the current task before shutting down
5. **Background Mode**: If running in background, use `kill <pid>` or `pkill -f run_service.py`

## Example Session

```bash
$ python3 run_service.py

============================================================
✨ Agent Assistant - CLI Mode ✨
============================================================

Commands:
  exit or quit     - Stop the service
  local or remote  - Force a specific model tier
  models           - List available remote models
  switch <number>  - Switch to a different remote model
  current          - Show current remote model

============================================================

❯ What is AI?
⠋ Thinking...

============================================================
🤖 Response (model: remote (google/gemini-2.5-pro-exp-03-25:free))
============================================================
Artificial Intelligence (AI) is...
============================================================

❯ exit

============================================================
👋 Thanks for using Agent Assistant!
============================================================
```
