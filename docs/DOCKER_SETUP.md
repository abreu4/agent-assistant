# Docker Code Execution Setup

Your Agent Assistant now has **improved Docker code execution** that works reliably when Docker is running.

## 🐳 What Was Fixed

### Previous Issues:
- Container cleanup race conditions
- Timeout handling problems
- Poor error messages when Docker not running

### Improvements Made:
1. ✅ Proper container lifecycle management
2. ✅ Better timeout handling with cleanup
3. ✅ Clear error messages for different failure modes
4. ✅ Proper log collection before container removal
5. ✅ Guaranteed cleanup with `finally` block

## 📦 Installing Docker

### For Ubuntu/Debian (WSL2):

```bash
# Update package list
sudo apt-get update

# Install prerequisites
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker service
sudo service docker start

# Test Docker installation
sudo docker run hello-world
```

### For WSL2 Specific Setup:

```bash
# Add your user to docker group (avoid sudo for docker commands)
sudo usermod -aG docker $USER

# Restart WSL to apply group changes
# (From Windows PowerShell: wsl --shutdown, then restart WSL)

# Start Docker on WSL startup (add to ~/.bashrc)
echo 'sudo service docker start' >> ~/.bashrc
```

## 🎯 Pull Required Image

The agent uses a lightweight Python image:

```bash
# Pull the Python image
sudo docker pull python:3.11-slim

# Verify it's available
docker images | grep python
```

**Image size:** ~130MB

## ✅ Test Docker Code Execution

### Quick Test:

```bash
# Test Docker manually
sudo docker run --rm python:3.11-slim python -c "print('Hello from Docker!')"
```

Expected output:
```
Hello from Docker!
```

### Test with Agent:

Create a test file `test_docker_execution.py`:

```python
#!/usr/bin/env python3
"""Test Docker code execution."""
import asyncio
from src.agent.workflow import HybridAgent

async def main():
    print("Testing Docker code execution...")

    agent = HybridAgent()
    await agent.initialize()

    # Test 1: Simple calculation
    print("\n=== Test 1: Simple calculation ===")
    result = await agent.run("Calculate the sum of numbers from 1 to 100 using Python code")
    print(agent.get_final_response(result))

    # Test 2: Data manipulation
    print("\n=== Test 2: List operations ===")
    result = await agent.run("Create a list of squares for numbers 1-10 in Python")
    print(agent.get_final_response(result))

    print("\n✅ All tests complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python3 test_docker_execution.py
```

## 🔧 Configuration Options

In `config/config.yaml`:

```yaml
tools:
  code_execution:
    enabled: true
    sandbox: "docker"      # Options: "docker", "restricted", "disabled"
    timeout: 30            # Maximum execution time (seconds)
    memory_limit: "256m"   # Memory limit per container
```

### Sandbox Options:

1. **docker** (Recommended)
   - Full isolation
   - Network disabled
   - Memory/CPU limits
   - Safest option

2. **restricted** (Not recommended)
   - Uses RestrictedPython
   - No true sandboxing
   - Less safe, but no Docker needed

3. **disabled**
   - Code execution disabled
   - Returns error message

## 🛡️ Security Features

The Docker sandbox includes:

- ✅ **Network disabled** - No internet access
- ✅ **Memory limits** - Default 256MB
- ✅ **CPU quotas** - 50% of single core
- ✅ **Auto-cleanup** - Containers removed after execution
- ✅ **Timeout protection** - 30s default limit
- ✅ **No filesystem access** - Isolated environment

## 🐛 Troubleshooting

### Error: "Docker is not running"

```bash
# Check Docker status
sudo service docker status

# Start Docker
sudo service docker start

# Test
sudo docker ps
```

### Error: "Image not found"

```bash
# Pull the image
sudo docker pull python:3.11-slim
```

### Error: "Permission denied"

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or restart WSL
wsl --shutdown  # From Windows
```

### Error: "Timeout"

Increase timeout in `config/config.yaml`:
```yaml
tools:
  code_execution:
    timeout: 60  # Increase to 60 seconds
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| Container startup | ~1-2s |
| Code execution | Depends on code |
| Total overhead | ~2-3s |
| Memory usage | <256MB per execution |

### Example Execution Times:
- Simple calculation: ~2s
- Data processing: ~3-5s
- Complex algorithm: ~5-10s

## 🎯 Usage Examples

### Example 1: Mathematics
**Prompt:** "Calculate the factorial of 20"

**Agent will:**
1. Detect this needs code execution
2. Generate Python code: `import math; print(math.factorial(20))`
3. Execute in Docker container
4. Return result: `2432902008176640000`

### Example 2: Data Processing
**Prompt:** "Generate first 10 Fibonacci numbers"

**Agent will:**
1. Write Fibonacci code
2. Execute in sandbox
3. Return: `[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]`

### Example 3: Text Processing
**Prompt:** "Count word frequency in this text: 'hello world hello'"

**Agent will:**
1. Write word counting code
2. Execute safely
3. Return frequency dict

## 🔍 Monitoring

Check Docker containers:
```bash
# Active containers
docker ps

# All containers (including stopped)
docker ps -a

# Container logs
docker logs <container_id>

# Clean up stopped containers
docker container prune
```

## 🚀 Advanced Configuration

### Custom Memory Limits

For memory-intensive tasks:
```yaml
tools:
  code_execution:
    memory_limit: "512m"  # Increase to 512MB
```

### Custom Timeout

For long-running tasks:
```yaml
tools:
  code_execution:
    timeout: 120  # 2 minutes
```

### Alternative Python Versions

Edit `src/agent/tools.py` (line 230):
```python
container = client.containers.run(
    "python:3.12-slim",  # Change version
    ...
)
```

Then pull new image:
```bash
docker pull python:3.12-slim
```

## ✨ What's Working Now

The improved implementation:

1. ✅ **Starts container** with proper configuration
2. ✅ **Waits for completion** with timeout
3. ✅ **Collects logs** (stdout + stderr)
4. ✅ **Checks exit code** for errors
5. ✅ **Cleans up container** even on error
6. ✅ **Handles timeouts** with kill + cleanup
7. ✅ **Reports errors clearly** with helpful messages

## 📝 Testing Checklist

- [ ] Docker installed
- [ ] Docker service running
- [ ] Python image pulled
- [ ] User in docker group (optional)
- [ ] Test container works: `docker run --rm python:3.11-slim python -c "print('OK')"`
- [ ] Agent code execution works

## 🎉 Ready to Use!

Once Docker is installed and running, your agent can safely execute Python code with full sandboxing!

**Example prompt to test:**
```
"Write and execute Python code to calculate pi using Monte Carlo method with 10000 samples"
```

The agent will write the code, execute it in Docker, and return the result!

---

**Last Updated:** 2025-12-03
**Version:** 1.1.0
