#!/usr/bin/env python3
"""Quick test script to verify agent is working."""

import sys
import asyncio
sys.path.insert(0, '/home/tiago/projects/agent_assistant')

from src.agent.workflow import HybridAgent
from src.utils.logging import setup_logging


async def test_agent():
    """Test the agent with a simple prompt."""
    print("=" * 70)
    print("Agent Prompt Test")
    print("=" * 70)
    print()

    # Setup logging
    logger = setup_logging(log_level='INFO', use_systemd=False)

    # Create and initialize agent
    print("🔧 Initializing agent...")
    agent = HybridAgent()

    print("🔥 Running warmup (testing and locking models)...")
    print()
    await agent.initialize()
    print()

    # Test prompt
    test_prompt = "What is Python? Give me a brief 2-sentence answer."

    print("=" * 70)
    print(f"📝 Prompt: {test_prompt}")
    print("=" * 70)
    print()

    # Run the agent
    print("🤖 Agent processing...")
    result = await agent.run(test_prompt)

    # Get response
    response = agent.get_final_response(result)
    model_used = result.get('model_used', 'unknown')

    print()
    print("=" * 70)
    print("✅ Response:")
    print("=" * 70)
    print()
    print(response)
    print()
    print("-" * 70)
    print(f"Model: {model_used}")
    print("-" * 70)
    print()

    # Test another prompt to verify memory management
    print("=" * 70)
    print("🔄 Testing follow-up (memory management)...")
    print("=" * 70)
    print()

    followup = "Can you explain that in even simpler terms?"
    print(f"📝 Follow-up: {followup}")
    print()

    result2 = await agent.run(followup)
    response2 = agent.get_final_response(result2)
    model_used2 = result2.get('model_used', 'unknown')

    print()
    print("=" * 70)
    print("✅ Response:")
    print("=" * 70)
    print()
    print(response2)
    print()
    print("-" * 70)
    print(f"Model: {model_used2}")
    print(f"Messages in context: {len(result2.get('messages', []))}")
    print("-" * 70)
    print()

    print("=" * 70)
    print("🎉 Agent is working! All systems operational!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(test_agent())
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
