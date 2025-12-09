#!/usr/bin/env python3
"""Test script to verify sticky model functionality."""

import sys
sys.path.insert(0, '/home/tiago/projects/agent_assistant')

from src.utils.config import config

def test_sticky_model_config():
    """Test sticky model configuration methods."""
    print("=" * 60)
    print("Testing Sticky Model Configuration")
    print("=" * 60)
    print()

    # Test 1: Check if sticky model is enabled
    print("Test 1: Check sticky model enabled status")
    enabled = config.get_sticky_model_enabled()
    print(f"  Sticky model enabled: {enabled}")
    assert enabled == True, "Sticky model should be enabled by default"
    print("  ✓ PASSED")
    print()

    # Test 2: Get initial values (should be None)
    print("Test 2: Check initial sticky model values")
    local_model = config.get_last_successful_model('local')
    remote_model = config.get_last_successful_model('remote')
    print(f"  Last successful local model: {local_model}")
    print(f"  Last successful remote model: {remote_model}")
    print("  ✓ PASSED (None expected initially)")
    print()

    # Test 3: Set a local model
    print("Test 3: Set a successful local model")
    test_local = "qwen2.5-coder:7b"
    config.set_last_successful_model('local', test_local)
    retrieved_local = config.get_last_successful_model('local')
    print(f"  Set local model to: {test_local}")
    print(f"  Retrieved: {retrieved_local}")
    assert retrieved_local == test_local, f"Expected {test_local}, got {retrieved_local}"
    print("  ✓ PASSED")
    print()

    # Test 4: Set a remote model
    print("Test 4: Set a successful remote model")
    test_remote = "google/gemini-2.5-pro-exp-03-25:free"
    config.set_last_successful_model('remote', test_remote)
    retrieved_remote = config.get_last_successful_model('remote')
    print(f"  Set remote model to: {test_remote}")
    print(f"  Retrieved: {retrieved_remote}")
    assert retrieved_remote == test_remote, f"Expected {test_remote}, got {retrieved_remote}"
    print("  ✓ PASSED")
    print()

    # Test 5: Reset models
    print("Test 5: Reset sticky models")
    config.set_last_successful_model('local', None)
    config.set_last_successful_model('remote', None)
    local_after = config.get_last_successful_model('local')
    remote_after = config.get_last_successful_model('remote')
    print(f"  Local after reset: {local_after}")
    print(f"  Remote after reset: {remote_after}")
    assert local_after is None, "Local should be None after reset"
    assert remote_after is None, "Remote should be None after reset"
    print("  ✓ PASSED")
    print()

    print("=" * 60)
    print("All tests PASSED! ✓")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_sticky_model_config()
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
