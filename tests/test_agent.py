#!/usr/bin/env python3
"""
Simple test script to test the agent without the hotkey functionality.
"""
import asyncio
from src.agent.workflow import HybridAgent


async def main():
    print("=" * 60)
    print("Agent Assistant - Test Mode")
    print("=" * 60)
    print()

    # Initialize agent
    print("Initializing agent...")
    agent = HybridAgent()
    await agent.initialize()
    print("Agent ready!")
    print()

    # Test queries
    test_queries = [
        "Hello!",  # Simple - should use local
        # "Explain quantum computing in detail",  # Complex - should use remote
        "What the fuck did you just fucking say about me you little bitch? I'll have you know that I graduated top of my class from the marines copy pasta info"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 60}")
        print(f"Test {i}/{len(test_queries)}: {query}")
        print('=' * 60)

        # Run query
        result = await agent.run(query)

        # Display results
        print(f"\nModel used: {result.get('model_used')}")
        print(f"Classification: {result.get('classification').complexity if result.get('classification') else 'N/A'}")
        print(f"\nResponse:")
        print("-" * 60)
        response = agent.get_final_response(result)
        print(response)
        print()

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
