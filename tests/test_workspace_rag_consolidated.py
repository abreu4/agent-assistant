#!/usr/bin/env python3
"""Comprehensive workspace RAG system test."""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.workspace_rag import get_workspace_rag
from src.utils.logging import setup_logging


async def test_workspace_rag():
    """Test the complete workspace RAG system."""
    print("=" * 70)
    print("Comprehensive Workspace RAG Test")
    print("=" * 70)
    print()

    # Setup logging
    logger = setup_logging(log_level='INFO', use_systemd=False)

    try:
        # Get RAG instance
        print("1. Initializing WorkspaceRAG...")
        rag = get_workspace_rag()
        print(f"   ✓ Workspace: {rag.workspace_dir}")
        print()

        # Test embedding initialization
        print("2. Testing embedding model...")
        embeddings = rag._get_embeddings()
        print(f"   ✓ Embeddings initialized: {type(embeddings).__name__}")
        
        # Test single embedding
        test_text = "This is a test embedding for workspace indexing"
        embedding = embeddings.embed_query(test_text)
        print(f"   ✓ Single embedding generated: {len(embedding)} dimensions")
        print()

        # Index workspace
        print("3. Indexing workspace...")
        indexed_count = rag.index_workspace()
        print(f"   ✓ Indexed {indexed_count} files")
        print()

        # Get file summary
        print("4. File summary:")
        summary = rag.get_file_summary()
        print(f"   {summary}")
        print()

        # Get file tree
        print("5. File tree (depth=2):")
        tree = rag.get_file_tree(max_depth=2)
        print(f"   {tree[:300]}...")
        print()

        # Test semantic search
        print("6. Semantic search tests:")
        test_queries = [
            "configuration yaml settings",
            "agent workflow",
            "memory management",
        ]

        for query in test_queries:
            print(f"\n   Query: '{query}'")
            results = rag.search(query, k=2)

            if results:
                for i, (doc, score) in enumerate(results, 1):
                    file_path = doc.metadata.get('file_path', 'unknown')
                    print(f"     [{i}] {file_path} (score: {1-score:.3f})")
                    print(f"         {doc.page_content[:80]}...")
            else:
                print("     No results found")

        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED - Workspace RAG system working!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_workspace_rag())
    sys.exit(0 if success else 1)
