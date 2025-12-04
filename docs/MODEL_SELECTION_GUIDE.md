# Model Selection Guide

Your Agent Assistant now supports **manual model override** through both config and GUI!

## ✨ What's New

### 1. Config-Based Override
Set a default model preference in `config/config.yaml`:

```yaml
llm:
  routing:
    force_model: null  # Options: null (auto), "local", or "remote"
```

**Examples:**
- `force_model: null` - Smart routing (default, recommended)
- `force_model: "local"` - Always use local Llama model
- `force_model: "remote"` - Always use Kimi K2

### 2. GUI Toggle Switch
When you press `Ctrl+Alt+Space`, you'll now see three options:

```
┌─────────────────────────────────────────┐
│  What can I help with?                  │
│  [_________________________________]    │
│                                         │
│  ┌─── Model Selection ────────────┐    │
│  │  ○ Auto (Smart Routing)        │    │
│  │  ○ Local Only (Fast & Free)    │    │
│  │  ○ Remote (Kimi K2)            │    │
│  └────────────────────────────────┘    │
│                                         │
│        [Submit]    [Cancel]             │
└─────────────────────────────────────────┘
```

## 📊 Model Comparison

| Model | Speed | Quality | Cost | Best For |
|-------|-------|---------|------|----------|
| **Auto** | Varies | High | Optimized | General use (recommended) |
| **Local** | Fast (~2s) | Good | FREE | Simple queries, dev work |
| **Remote** | Slower (~5s) | Best | $0.60/M tokens | Complex analysis, creative writing |

## 🎯 Usage Examples

### Example 1: Always Use Local (Development)

**Config:**
```yaml
force_model: "local"
```

**Use Case:**
- Working offline
- Testing the agent
- Simple file operations
- Quick coding assistance

### Example 2: Always Use Remote (Quality First)

**Config:**
```yaml
force_model: "remote"
```

**Use Case:**
- Research and analysis
- Creative writing
- Complex problem-solving
- Don't care about cost

### Example 3: Smart Routing (Default)

**Config:**
```yaml
force_model: null
prefer_local: true
```

**Behavior:**
- "Hello!" → Local (simple)
- "Explain recursion" → Local (medium)
- "Write a detailed analysis of quantum computing" → Remote (complex)
- "Debug this code" → Local (code)

**Cost:** ~$20-30/month for normal use

## 🧪 Testing the Feature

Run the test script:
```bash
python3 test_force_model.py
```

This demonstrates:
1. Auto routing behavior
2. Forcing local for complex queries
3. Forcing remote for simple queries

## 🎨 GUI Toggle Details

The GUI toggle **overrides** both the config setting and automatic routing:

1. **Auto (Smart Routing)** - Default
   - Uses classification to route intelligently
   - Respects `prefer_local` config
   - Most cost-effective

2. **Local Only (Fast & Free)** - Forces local
   - Always uses Llama 3.1 8B
   - No API costs
   - Good for 90% of queries

3. **Remote (Kimi K2)** - Forces remote
   - Always uses Kimi K2
   - Best quality responses
   - Incurs API costs (~$0.60/M input tokens)

## 🔧 How It Works Internally

### Priority Order:
1. **GUI Toggle** (highest priority)
2. **Config force_model**
3. **Automatic Routing** (lowest priority)

### Code Example:
```python
# In your code
result = await agent.run(
    "Explain quantum computing",
    force_model="remote"  # Override to remote
)
```

### Routing Logic:
```python
# src/agent/router.py (simplified)
def route(self, classification, force_model=None):
    # Check GUI/parameter override
    if force_model in ['local', 'remote']:
        return force_model

    # Check config override
    force = config.get('llm.routing.force_model')
    if force in ['local', 'remote']:
        return force

    # Automatic routing
    if classification == SIMPLE:
        return "local"
    elif classification == COMPLEX:
        return "remote"
    # ... etc
```

## 💰 Cost Optimization Tips

### Maximize Free Usage:
```yaml
force_model: "local"
```
**Savings:** 100% free, but lower quality on complex queries

### Balanced Approach (Recommended):
```yaml
force_model: null
prefer_local: true
```
**Savings:** ~70-80% queries free, $20-30/month

### Quality First:
```yaml
force_model: "remote"
```
**Cost:** ~$50-100/month for heavy use

## 🚀 Quick Start

1. **Try the GUI toggle** (easiest way):
   ```bash
   sudo python3 run_service.py
   # Press Ctrl+Alt+Space
   # Select model preference
   ```

2. **Set config default** (for persistent preference):
   ```bash
   nano config/config.yaml
   # Set force_model: "local" or "remote"
   ```

3. **Use programmatically** (for scripts):
   ```python
   result = await agent.run(query, force_model="local")
   ```

## 📝 Configuration Reference

**File:** `config/config.yaml`

```yaml
llm:
  routing:
    prefer_local: true           # When auto, prefer local for medium tasks
    cost_limit_monthly: 50       # Budget tracking (USD)
    force_model: null            # Override: null, "local", or "remote"
```

## ❓ FAQ

**Q: Which model is best?**
A: Start with **Auto** - it gives you the best balance of cost and quality.

**Q: How do I save money?**
A: Use **Local Only** for 90% of queries, only switch to Remote for complex analysis.

**Q: I want the best answers always.**
A: Set `force_model: "remote"` in config or always select "Remote" in GUI.

**Q: Does the GUI toggle persist?**
A: No, it resets to "Auto" each time you open the popup. Set `force_model` in config for persistence.

**Q: Can I see which model was used?**
A: Yes! The result window shows "Model: local" or "Model: remote" at the top.

## 🎉 Summary

You now have **three ways** to control model selection:

1. ⚙️ **Config file** - Set default behavior
2. 🖱️ **GUI toggle** - Per-query override
3. 💻 **Code parameter** - Programmatic control

All three methods work together with clear priority ordering!

---

**Last Updated:** 2025-12-03
**Version:** 1.1.0
