# Agent Assistant - Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY run_service.py .

# Copy .env if it exists (optional, can be mounted as volume)
COPY .env* ./

# Create workspace directory
RUN mkdir -p /app/workspace

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

# Expose any ports if needed (for future web interface)
# EXPOSE 8000

# Default command runs CLI service
CMD ["python3", "run_service.py"]
