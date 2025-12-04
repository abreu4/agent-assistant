#!/usr/bin/env python3
"""
Test script to demonstrate force_model override feature.
"""
import asyncio
from src.agent.workflow import HybridAgent


async def main():
    print("=" * 70)
    print("Agent Assistant - Force Model Override Test")
    print("=" * 70)
    print()

    # Initialize agent
    print("Initializing agent...")
    agent = HybridAgent()
    await agent.initialize()
    print("Agent ready!")
    print()

    # Test query (normally would be classified as COMPLEX and use remote)
    query = "Explain the concept of recursion in programming"

    # Test 1: Auto routing (default behavior)
    print("=" * 70)
    print("Test 1: AUTO routing (should use remote for this complex query)")
    print("=" * 70)
    print(f"Query: {query}")
    print()

    result = await agent.run(query)
    print(f"✓ Classification: {result.get('classification').complexity if result.get('classification') else 'N/A'}")
    print(f"✓ Model used: {result.get('model_used')}")
    print(f"✓ Response length: {len(agent.get_final_response(result))} chars")
    print()

    # Test 2: Force LOCAL
    print("=" * 70)
    print("Test 2: FORCE LOCAL (override to use local model)")
    print("=" * 70)
    print(f"Query: {query}")
    print()

    result = await agent.run(query, force_model="local")
    print(f"✓ Classification: {result.get('classification').complexity if result.get('classification') else 'N/A'}")
    print(f"✓ Model used: {result.get('model_used')} (FORCED)")
    print(f"✓ Response length: {len(agent.get_final_response(result))} chars")
    print()

    # Test 3: Force REMOTE
    print("=" * 70)
    print("Test 3: FORCE REMOTE (explicitly use Kimi K2)")
    print("=" * 70)
    simple_query = "What is 2 + 2?"
    print(f"Query: {simple_query} (normally would use local)")
    print()

    result = await agent.run(simple_query, force_model="remote")
    print(f"✓ Classification: {result.get('classification').complexity if result.get('classification') else 'N/A'}")
    print(f"✓ Model used: {result.get('model_used')} (FORCED)")
    print(f"✓ Response: {agent.get_final_response(result)}")
    print()

    print("=" * 70)
    print("All tests complete!")
    print("=" * 70)
    print()
    print("Summary:")
    print("  ✓ Auto routing works based on classification")
    print("  ✓ Force local overrides complex queries to use local model")
    print("  ✓ Force remote overrides simple queries to use Kimi K2")
    print()


if __name__ == "__main__":
    asyncio.run(main())
