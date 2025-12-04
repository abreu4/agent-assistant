# Docker Deployment Guide

This guide explains how to run Agent Assistant in Docker containers.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Ollama running on host machine (for local models)

## Quick Start

### 1. Ensure Ollama is Running on Host

```bash
# Start Ollama on host
ollama serve

# Verify it's accessible
curl http://localhost:11434/api/tags
```

### 2. Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your API keys (optional)
nano .env
```

### 3. Build and Run

```bash
# Build the image
docker-compose build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 4. Use the CLI

```bash
# Attach to running container
docker attach agent-assistant

# Or run interactively
docker-compose run --rm agent-assistant
```

## Running Tests in Docker

```bash
# Run all tests
docker-compose run --rm agent-assistant pytest tests/ -v

# Run specific test
docker-compose run --rm agent-assistant pytest tests/test_agent.py -v

# Run with coverage
docker-compose run --rm agent-assistant pytest tests/ --cov=src
```

## Docker Images

### Building Custom Image

```bash
# Build with tag
docker build -t agent-assistant:latest .

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.12 -t agent-assistant:py312 .
```

### Running Without Docker Compose

```bash
# Run with environment variables
docker run -it --rm \
  --name agent-assistant \
  -e OPENROUTER_API_KEY=${OPENROUTER_API_KEY} \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  --add-host host.docker.internal:host-gateway \
  -v $(pwd)/workspace:/app/workspace \
  agent-assistant:latest
```

## Configuration

### Environment Variables

All environment variables can be set in `.env` file or passed directly:

```yaml
# docker-compose.yml
environment:
  - OPENROUTER_API_KEY=sk-or-v1-...
  - ANTHROPIC_API_KEY=sk-ant-...
  - LOG_LEVEL=DEBUG
```

### Volumes

```yaml
volumes:
  # Workspace persistence
  - ./workspace:/app/workspace
  
  # Config updates (read-only)
  - ./config:/app/config:ro
  
  # Environment variables (read-only)
  - ./.env:/app/.env:ro
```

### Networking

The container needs to access Ollama on the host:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"

environment:
  - OLLAMA_BASE_URL=http://host.docker.internal:11434
```

For Linux, you may need to use the host's IP:

```bash
# Find host IP
ip addr show docker0

# Use in docker-compose.yml
environment:
  - OLLAMA_BASE_URL=http://172.17.0.1:11434
```

## Production Deployment

### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml agent-assistant

# Check services
docker service ls

# View logs
docker service logs agent-assistant_agent-assistant

# Remove stack
docker stack rm agent-assistant
```

### Using Kubernetes

Create deployment manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-assistant
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent-assistant
  template:
    metadata:
      labels:
        app: agent-assistant
    spec:
      containers:
      - name: agent-assistant
        image: agent-assistant:latest
        env:
        - name: OPENROUTER_API_KEY
          valueFrom:
            secretKeyRef:
              name: agent-secrets
              key: openrouter-key
        - name: OLLAMA_BASE_URL
          value: "http://ollama-service:11434"
        volumeMounts:
        - name: workspace
          mountPath: /app/workspace
      volumes:
      - name: workspace
        persistentVolumeClaim:
          claimName: agent-workspace
```

## Multi-Architecture Support

### Building for Multiple Platforms

```bash
# Enable buildx
docker buildx create --use

# Build for AMD64 and ARM64
docker buildx build --platform linux/amd64,linux/arm64 \
  -t agent-assistant:latest \
  --push .
```

## Troubleshooting

### Cannot Connect to Ollama

**Problem**: Container can't reach Ollama on host

**Solutions**:

1. Linux: Use host network mode
```bash
docker run --network host agent-assistant:latest
```

2. macOS/Windows: Ensure host.docker.internal works
```bash
docker run --add-host host.docker.internal:host-gateway agent-assistant:latest
```

3. Check Ollama is listening on all interfaces
```bash
# Edit Ollama config to bind to 0.0.0.0
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Permission Issues with Volumes

**Problem**: Container can't write to mounted workspace

**Solution**:

```bash
# Create workspace with proper permissions
mkdir -p workspace
chmod 777 workspace

# Or use named volume instead
volumes:
  - agent-workspace:/app/workspace
```

### Out of Memory

**Problem**: Container OOM killed when loading models

**Solution**: Increase Docker memory limit

```bash
# In docker-compose.yml
services:
  agent-assistant:
    mem_limit: 16g
    memswap_limit: 16g
```

Or configure in Docker Desktop settings (minimum 8GB recommended).

### Environment Variables Not Loading

**Problem**: API keys not working in container

**Solutions**:

1. Check .env file exists
```bash
ls -la .env
```

2. Verify syntax (no spaces around =)
```bash
# Good
OPENROUTER_API_KEY=sk-or-v1-...

# Bad
OPENROUTER_API_KEY = sk-or-v1-...
```

3. Check docker-compose loads .env
```bash
docker-compose config | grep -A 5 environment
```

## Performance Tips

### Image Size Optimization

The image is already optimized with:
- Python slim base (~150MB)
- Multi-stage build not needed (no compilation)
- .dockerignore excludes unnecessary files

Current image size: ~500-600MB

### Startup Time

First run is slower due to:
- Model warmup
- Package imports

Subsequent runs are faster with:
- Container restart (keeps warmed state)
- Volume caching

### Resource Limits

Recommended limits:

```yaml
services:
  agent-assistant:
    mem_limit: 16g        # For multiple local models
    cpus: 4               # For parallel processing
```

Minimum requirements:
- Memory: 8GB (for one local model)
- CPUs: 2

## CI/CD Integration

### GitHub Actions

```yaml
name: Docker Build

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t agent-assistant:test .
      
      - name: Run tests in container
        run: |
          docker run --rm agent-assistant:test \
            pytest tests/ --cov=src
```

### GitLab CI

```yaml
docker-build:
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG .
    - docker run --rm $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG pytest tests/
```

## Security Considerations

1. **Don't commit .env** - Use secrets management
2. **Read-only volumes** - Mount config as ro when possible
3. **Non-root user** - Consider adding USER directive
4. **Network isolation** - Use Docker networks
5. **Resource limits** - Prevent resource exhaustion

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Ollama Docker Guide](https://hub.docker.com/r/ollama/ollama)
