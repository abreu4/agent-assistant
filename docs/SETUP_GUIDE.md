# Setup Guide - Agent Assistant

## ✅ What's Already Done

- [x] Project structure created
- [x] All Python dependencies installed
- [x] Configuration files created
- [x] All modules tested and working
- [x] .env file created (needs your API key)

## 🔧 What You Need to Do

### 1. Install Ollama (Required for Local Models)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

### 2. Pull Ollama Models

```bash
# Main local model (7GB) - this will take a few minutes
ollama pull llama3.1:8b

# Fast classifier (2GB)
ollama pull llama3.2:3b

# Fallback model (4GB)
ollama pull mistral:7b
```

**Total download size: ~13GB**

### 3. Get API Key for Kimi K2

**Option A: OpenRouter (Recommended - Easier)**
1. Go to https://openrouter.ai
2. Sign up for an account
3. Go to Keys section
4. Create a new API key
5. Add credits to your account ($5-10 is a good start)

**Option B: Moonshot AI (Direct)**
1. Go to https://platform.moonshot.cn
2. Sign up (may require Chinese phone number)
3. Create API key
4. Add to account balance

### 4. Update .env File

```bash
# Edit the .env file
nano .env

# Replace this line:
OPENROUTER_API_KEY=your-key-here-replace-me

# With your actual key:
OPENROUTER_API_KEY=sk-or-v1-abc123...
```

Save and exit (Ctrl+X, then Y, then Enter)

### 5. Test the Service

```bash
# Run in foreground to test
python3 src/service.py
```

You should see:
```
======================================================================
Agent Assistant Service Starting
======================================================================
Warming up models...
Local models warmed up successfully
All components started successfully
Hotkey: ctrl+alt+space
Service is ready!
```

**Test the hotkey:**
- Press `Ctrl+Alt+Space`
- Popup window should appear
- Type a simple question: "What is Python?"
- Press Enter
- Result window should show the answer

**Note:** The first time may take 10-20 seconds as models load.

### 6. Grant Keyboard Permissions (Required for Hotkey)

The hotkey listener needs special permissions to detect global keyboard events:

```bash
# Grant capabilities to Python
sudo setcap cap_net_admin+ep $(which python3)

# Verify
getcap $(which python3)
# Should show: cap_net_admin+ep
```

**If you don't grant permissions:** The service will fail with "Permission denied" when trying to register the hotkey.

### 7. Install as Background Service (Optional)

Once everything works, install it as a systemd service to run in the background:

```bash
# Copy service file
sudo cp config/agent_assistant.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable to start on boot
sudo systemctl enable agent_assistant

# Start the service
sudo systemctl start agent_assistant

# Check status
sudo systemctl status agent_assistant

# View logs
journalctl -u agent_assistant -f
```

## 🎯 Quick Test

After completing setup, test the full workflow:

1. **Simple query (should use local model):**
   - Press `Ctrl+Alt+Space`
   - Type: "Hello"
   - Should respond quickly using local Llama model

2. **Complex query (should use remote Kimi K2):**
   - Press `Ctrl+Alt+Space`
   - Type: "Explain quantum computing in detail"
   - Should use remote Kimi K2 model (check result window for "Model: remote")

3. **Tool usage (file operations):**
   - Press `Ctrl+Alt+Space`
   - Type: "Create a file called test.txt with the content 'Hello World'"
   - Should create file in `/home/tiago/agent_workspace/test.txt`

## 🐛 Troubleshooting

### Ollama Not Running

```bash
# Check if Ollama is running
ollama list

# If not, start it
ollama serve &
```

### Permission Denied for Hotkey

```bash
# Re-grant permissions
sudo setcap cap_net_admin+ep $(which python3)

# Or run service with sudo (not recommended)
sudo python3 src/service.py
```

### API Key Not Working

```bash
# Test OpenRouter API
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"

# Should return JSON with available models
```

### GUI Not Showing

```bash
# Check DISPLAY variable
echo $DISPLAY  # Should show :0 or similar

# For WSL2, may need to set up X11 forwarding
export DISPLAY=:0
```

### Models Taking Too Long to Load

First run is slow as models load into memory. Subsequent runs are faster.

To keep models loaded:
```bash
# Pre-load models
ollama run llama3.1:8b &
```

## 📊 Expected Costs

- **Local queries:** FREE (70-80% of queries)
- **Remote queries:** ~$0.60/M input, $2.50/M output tokens
- **Monthly (personal use):** $20-30

## 🎉 You're Ready!

Once you've completed these steps, your agent should be fully functional!

Press `Ctrl+Alt+Space` anytime to summon your AI assistant.

## Next Steps

- Customize hotkey in `config/config.yaml`
- Adjust routing preferences
- Add custom tools in `src/agent/tools.py`
- Check logs: `journalctl -u agent_assistant -f`

---

**Need help?** Check the README.md for detailed documentation.
