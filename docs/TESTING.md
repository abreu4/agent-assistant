# Testing Guide

This document describes how to run tests for the Agent Assistant project.

## Test Structure

All tests are located in the `tests/` directory:

```
tests/
├── test_agent.py          # Core agent functionality tests
└── test_force_model.py    # Model forcing and routing tests
```

## Prerequisites

Ensure you have installed all dependencies:

```bash
pip install -r requirements.txt
```

For testing, you may need additional packages:

```bash
pip install pytest pytest-asyncio
```

## Running Tests

### Run All Tests

```bash
# From project root
python3 -m pytest tests/

# With verbose output
python3 -m pytest tests/ -v

# With coverage report
python3 -m pytest tests/ --cov=src --cov-report=html
```

### Run Specific Test File

```bash
# Test agent functionality
python3 -m pytest tests/test_agent.py

# Test model forcing
python3 -m pytest tests/test_force_model.py
```

### Run Specific Test Function

```bash
# Run a specific test
python3 -m pytest tests/test_agent.py::test_function_name -v
```

## Running Individual Test Scripts

Some test files can be run directly:

```bash
# Run force model test
python3 tests/test_force_model.py

# Run agent test
python3 tests/test_agent.py
```

## Test Configuration

### Environment Setup

Tests use the same `.env` file as the main application. Ensure you have:

1. **Local Model**: Ollama running with at least one model installed
2. **Remote Model** (optional): API key configured in `.env`

```bash
# Required for remote model tests
OPENROUTER_API_KEY=your-key-here
```

### Test Data

Tests use the configuration from `config/config.yaml`. You may want to:

- Use smaller/faster models for testing
- Reduce timeout values for faster test execution
- Ensure local models are available

## Common Test Scenarios

### Test Local Model Only

```bash
# Force local model in config
# Set force_model: local in config.yaml
python3 -m pytest tests/test_agent.py -v
```

### Test Remote Model Only

```bash
# Force remote model in config
# Set force_model: remote in config.yaml
python3 -m pytest tests/test_agent.py -v
```

### Test Model Switching

```bash
# Run the force model test specifically
python3 tests/test_force_model.py
```

## Troubleshooting

### Ollama Not Running

If tests fail with connection errors:

```bash
# Start Ollama
ollama serve

# Verify models are installed
ollama list
```

### Remote API Errors

If remote model tests fail:

1. Check API key is valid in `.env`
2. Verify you have credits/quota
3. Check network connectivity
4. Try a different remote model

### Async Warnings

If you see warnings about event loops:

```bash
# Install pytest-asyncio
pip install pytest-asyncio
```

## Writing New Tests

### Test File Template

```python
"""Test description."""
import asyncio
import pytest
from src.agent.workflow import HybridAgent

@pytest.mark.asyncio
async def test_your_feature():
    """Test description."""
    agent = HybridAgent()
    await agent.initialize()

    result = await agent.run("test query")

    assert result is not None
    # Add your assertions
```

### Best Practices

1. **Use pytest fixtures** for common setup
2. **Mark async tests** with `@pytest.mark.asyncio`
3. **Clean up resources** in teardown
4. **Mock external APIs** when appropriate
5. **Test both success and failure cases**

## Continuous Integration

To run tests in CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest tests/ --cov=src
```

## Test Coverage

Generate coverage report:

```bash
# HTML report
pytest tests/ --cov=src --cov-report=html

# View in browser
open htmlcov/index.html
```

## Test Modes

### Quick Test (Local Only)

```bash
# Test with local models only (fast)
pytest tests/ -m "not remote"
```

### Full Test (Local + Remote)

```bash
# Test everything (requires API keys)
pytest tests/ -v
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [LangChain testing guide](https://python.langchain.com/docs/contributing/testing)
