# Remote Model Retry Strategy

## Overview

The Agent Assistant now implements an intelligent retry mechanism that tries up to 3 different remote models before falling back to the local model. This ensures maximum resilience when dealing with free OpenRouter models that may be rate-limited or temporarily unavailable.

## How It Works

### Retry Flow

1. **Initial Request**
   - System routes the query to the appropriate model tier (local or remote) based on task complexity
   - If routed to remote, uses the currently configured remote model

2. **First Failure (Remote Model)**
   - If the remote model fails (rate limit, timeout, error), the system automatically switches to the next available remote model
   - Tracks which models have been tried to avoid retrying the same model
   - Logs: `"Trying next remote model (attempt 1/3)"`

3. **Second Failure (Remote Model)**
   - Switches to a third untried remote model
   - Logs: `"Trying next remote model (attempt 2/3)"`

4. **Third Failure (Remote Model)**
   - Switches to a fourth untried remote model (if available)
   - Logs: `"Trying next remote model (attempt 3/3)"`

5. **All Remote Models Failed**
   - After 3 different remote models have been tried and all failed
   - Falls back to the local model
   - Logs: `"All 3 remote models failed, falling back to local"`

6. **Local Model Execution**
   - Processes the query using the local Ollama model
   - If local fails, returns error after exhausting all options

## State Tracking

The system maintains the following state during retries:

- `remote_models_tried`: List of remote model IDs that have been attempted
- `remote_retry_count`: Number of times we've retried with different remote models
- `retry_count`: Total number of retries (across all model tiers)

## Example Scenario

```
User Query: "Explain quantum computing"
└─> Classified as: COMPLEX
    └─> Routed to: REMOTE
        ├─> Try #1: Google Gemini 2.5 Pro Exp → FAILED (rate limited)
        ├─> Try #2: Meta Llama 4 Maverick → FAILED (timeout)
        ├─> Try #3: DeepSeek Chat V3 → SUCCESS ✓
        └─> Response delivered
```

## Alternative Scenario (All Fail)

```
User Query: "Write a complex analysis"
└─> Classified as: COMPLEX
    └─> Routed to: REMOTE
        ├─> Try #1: Google Gemini 2.5 Pro Exp → FAILED
        ├─> Try #2: Meta Llama 4 Maverick → FAILED
        ├─> Try #3: DeepSeek Chat V3 → FAILED
        └─> Fallback to: LOCAL (llama3.1:8b) → SUCCESS ✓
```

## Benefits

1. **Resilience**: Multiple fallback options ensure queries succeed even when services are degraded
2. **Zero Cost**: All remote models are free tier, no cost for retries
3. **Automatic**: No user intervention required
4. **Smart**: Doesn't retry the same failed model
5. **Transparent**: Logs show which models are being tried

## Configuration

The 10 available remote models are configured in `config/config.yaml`:

1. Google Gemini 2.5 Pro Exp (default)
2. Meta Llama 4 Maverick
3. DeepSeek Chat V3
4. Mistral Small 3.1
5. DeepSeek R1 Zero
6. NVIDIA Nemotron Nano 8B
7. Meta Llama 4 Scout
8. Qwen 2.5 VL
9. DeepHermes 3
10. Kimi K2

The system will cycle through these models in order until one succeeds or 3 have been tried.

## Monitoring

Check the logs to see the retry behavior in action:

```bash
python3 run_service.py
```

Look for log entries like:
- `"Executing with remote model: Gemini 2.5 Pro Exp (1/3 tried)"`
- `"Trying next remote model (attempt 2/3)"`
- `"All 3 remote models failed, falling back to local"`
