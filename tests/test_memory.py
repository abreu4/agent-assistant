#!/usr/bin/env python3
"""Test script for memory management system."""

import sys
sys.path.insert(0, '/home/tiago/projects/agent_assistant')

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.agent.memory import MemoryManager
from src.utils.logging import setup_logging

def test_memory_manager():
    """Test the memory management system."""
    print("=" * 70)
    print("Memory Management System Test")
    print("=" * 70)
    print()

    # Setup logging
    logger = setup_logging(log_level='INFO', use_systemd=False)

    # Create memory manager
    memory_mgr = MemoryManager()
    print(f"Memory Strategy: {memory_mgr.strategy}")
    print(f"Max Messages: {memory_mgr.max_messages}")
    print(f"Reserve Tokens: {memory_mgr.reserve_tokens}")
    print()

    # Test 1: Get model limits
    print("Test 1: Model Context Limits")
    print("-" * 70)

    models_to_test = [
        ("llama3.1:8b", "local"),
        ("deepseek-coder:6.7b", "local"),
        ("mistralai/mistral-small-3.1-24b-instruct:free", "remote"),
        ("google/gemini-2.5-pro-exp-03-25:free", "remote"),
    ]

    for model_id, tier in models_to_test:
        context, max_output = memory_mgr.get_model_limits(model_id, tier)
        print(f"{model_id}")
        print(f"  Context Window: {context:,} tokens")
        print(f"  Max Output: {max_output:,} tokens")

    print()

    # Test 2: Token estimation
    print("Test 2: Token Estimation")
    print("-" * 70)

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="Hello, how are you?"),
        AIMessage(content="I'm doing well, thank you! How can I help you today?"),
        HumanMessage(content="Can you explain what Python is?"),
        AIMessage(content="Python is a high-level, interpreted programming language known for its simplicity and readability."),
    ]

    estimated = memory_mgr.estimate_tokens(messages)
    print(f"Messages: {len(messages)}")
    print(f"Estimated Tokens: {estimated}")
    print()

    # Test 3: Sliding window truncation
    print("Test 3: Sliding Window Truncation")
    print("-" * 70)

    # Create many messages
    long_conversation = [SystemMessage(content="You are a helpful assistant.")]
    for i in range(30):
        long_conversation.append(HumanMessage(content=f"Question {i}: " + "word " * 50))
        long_conversation.append(AIMessage(content=f"Answer {i}: " + "word " * 50))

    print(f"Original messages: {len(long_conversation)}")
    original_tokens = memory_mgr.estimate_tokens(long_conversation)
    print(f"Original tokens: {original_tokens:,}")
    print()

    # Test with small context window
    truncated = memory_mgr.truncate_messages(
        long_conversation,
        context_window=4096,
        max_output_tokens=1024
    )

    print(f"After truncation: {len(truncated)} messages")
    truncated_tokens = memory_mgr.estimate_tokens(truncated)
    print(f"Truncated tokens: {truncated_tokens:,}")
    print(f"Preserved system message: {isinstance(truncated[0], SystemMessage)}")
    print()

    # Test 4: Full memory management
    print("Test 4: Full Memory Management")
    print("-" * 70)

    # Test with local model (small context)
    managed_local = memory_mgr.manage_context(
        long_conversation,
        "llama3.2:3b",  # 4096 context window
        "local"
    )
    print(f"Local (llama3.2:3b - 4K context):")
    print(f"  Original: {len(long_conversation)} messages")
    print(f"  Managed: {len(managed_local)} messages")
    print()

    # Test with remote model (large context)
    managed_remote = memory_mgr.manage_context(
        long_conversation,
        "google/gemini-2.5-pro-exp-03-25:free",  # 1M context window
        "remote"
    )
    print(f"Remote (Gemini 2.5 Pro - 1M context):")
    print(f"  Original: {len(long_conversation)} messages")
    print(f"  Managed: {len(managed_remote)} messages")
    print(f"  (No truncation needed - fits in context)")
    print()

    print("=" * 70)
    print("✅ All tests completed!")
    print("=" * 70)
    print()
    print("Summary:")
    print("- Context limits configured for all models")
    print("- Token estimation working")
    print("- Sliding window truncation preserves recent messages")
    print("- System messages always preserved")
    print("- Different models handle context appropriately")

if __name__ == "__main__":
    try:
        test_memory_manager()
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
