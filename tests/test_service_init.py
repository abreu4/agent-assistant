#!/usr/bin/env python3
"""Test service initialization with workspace indexing."""
import asyncio
import sys
import os

# Set up environment
os.chdir('/home/tiago/projects/agent_assistant')
sys.path.insert(0, '/home/tiago/projects/agent_assistant/src')

async def test_initialization():
    """Test the service initialization including workspace indexing."""
    print("Testing Agent Service Initialization")
    print("=" * 60)

    try:
        # Import after path setup
        from agent.workflow import AgentWorkflow
        from utils.config import config
        from utils.logging import get_logger

        logger = get_logger("test")

        print("\n1. Initializing AgentWorkflow...")
        workflow = AgentWorkflow()
        print("   ✓ Workflow created")

        print("\n2. Running workflow initialization (includes warmup + indexing)...")
        await workflow.initialize()
        print("   ✓ Initialization complete")

        print("\n3. Checking workspace RAG status...")
        from agent.workspace_rag import get_workspace_rag
        rag = get_workspace_rag()
        summary = rag.get_file_summary()
        print(f"\n{summary}")

        print("\n4. Testing semantic search...")
        results = rag.search("python configuration yaml", k=3)
        print(f"   ✓ Search found {len(results)} results")

        if results:
            print("\n   Top results:")
            for i, (doc, score) in enumerate(results[:3], 1):
                file_path = doc.metadata.get('file_path', 'unknown')
                print(f"   {i}. {file_path} (score: {score:.4f})")

        print("\n" + "=" * 60)
        print("✅ SERVICE INITIALIZATION SUCCESSFUL!")
        print("   Workspace indexing is working correctly")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_initialization())
    sys.exit(0 if success else 1)
