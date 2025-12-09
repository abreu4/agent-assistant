#!/usr/bin/env python3
"""Test script to verify OpenAI configuration."""

import sys
sys.path.insert(0, '/home/tiago/projects/agent_assistant')

from src.utils.config import config
from src.utils.logging import setup_logging


def test_openai_config():
    """Test OpenAI model configuration."""
    print("=" * 70)
    print("OpenAI Configuration Test")
    print("=" * 70)
    print()

    # Setup logging
    logger = setup_logging(log_level='INFO', use_systemd=False)

    # Get remote models
    remote_models = config.get_available_remote_models()

    # Find OpenAI models
    openai_models = [m for m in remote_models if m.get('provider') == 'openai']

    print(f"Found {len(openai_models)} OpenAI models configured:")
    print()

    for model in openai_models:
        print(f"✓ {model['name']} ({model['id']})")
        print(f"  Context: {model['context_window']:,} tokens")
        print(f"  Max Output: {model['max_output_tokens']:,} tokens")
        print(f"  Description: {model['description']}")
        print()

    # Check base URL
    remote_config = config.get_llm_config('remote')
    openai_base = remote_config.get('openai_base')
    print(f"OpenAI Base URL: {openai_base}")
    print()

    # Check API key (don't print it!)
    openai_key = config.get_api_key('openai')
    if openai_key and openai_key != "EMPTY":
        print("✓ OpenAI API key found in environment")
    else:
        print("⚠️  OpenAI API key not found")
        print("   Set OPENAI_API_KEY in your .env file to use OpenAI models")
    print()

    print("=" * 70)
    print("Available OpenAI Models:")
    print("=" * 70)
    print()
    print("Flagship Models:")
    print("  • GPT-4o - Fastest and most affordable flagship (128K context)")
    print("  • GPT-4 Turbo - Latest GPT-4 with vision (128K context)")
    print()
    print("Affordable Models:")
    print("  • GPT-4o Mini - Small, fast, affordable (128K context)")
    print("  • GPT-3.5 Turbo - Fast for simple tasks (16K context)")
    print()
    print("Reasoning Models:")
    print("  • O1 - Complex reasoning and problem solving (200K context)")
    print("  • O1 Mini - Faster, cheaper reasoning (128K context)")
    print()

    print("=" * 70)
    print("✅ OpenAI configuration ready!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_openai_config()
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
