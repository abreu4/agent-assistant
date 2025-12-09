"""RAG system for workspace file awareness and semantic search."""
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from ..utils.config import config
from ..utils.logging import get_logger
from .custom_embeddings import DirectOllamaEmbeddings

logger = get_logger("workspace_rag")


class WorkspaceRAG:
    """
    RAG system for workspace file indexing and semantic search.

    Indexes code and text files in the workspace directory,
    providing semantic search capabilities for the agent.
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        """
        Initialize workspace RAG system.

        Args:
            workspace_dir: Workspace directory to index (default: from config)
        """
        self.workspace_dir = Path(workspace_dir or config.get_workspace_dir())
        self.vectorstore: Optional[Chroma] = None
        self.embeddings = None
        self.indexed_files: Dict[str, str] = {}  # filepath -> hash
        self.index_dir = self.workspace_dir / ".agent_index"

        # File patterns to include/exclude
        self.include_extensions = config.get('tools.file_operations.allowed_extensions', [
            '.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml',
            '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.sh'
        ])
        self.exclude_patterns = [
            '__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules',
            '.pytest_cache', '.mypy_cache', 'dist', 'build', '.egg-info',
            '.agent_index', '.tox', '.eggs', '*.egg-info', '.coverage',
            'htmlcov', '.hypothesis', '.cache', 'site-packages'
        ]

        logger.debug(f"Workspace RAG initialized for repository: {self.workspace_dir}")

    def _get_embeddings(self):
        """Get or create embeddings model."""
        if self.embeddings is None:
            # Use local Ollama embeddings for privacy and speed
            try:
                self.embeddings = DirectOllamaEmbeddings(
                    model="nomic-embed-text",  # Fast, good quality embedding model
                    base_url=config.get('llm.local.base_url', 'http://localhost:11434')
                )
                logger.debug("Using nomic-embed-text for embeddings")
            except Exception as e:
                logger.warning(f"Failed to load nomic-embed-text: {e}")
                # Fallback to basic embeddings
                try:
                    self.embeddings = DirectOllamaEmbeddings(
                        model="llama3.2:3b",  # Use smallest available model
                        base_url=config.get('llm.local.base_url', 'http://localhost:11434')
                    )
                    logger.debug("Fallback to llama3.2:3b for embeddings")
                except Exception as e2:
                    logger.error(f"Failed to initialize embeddings: {e2}")
                    raise

        return self.embeddings

    def _should_index_file(self, filepath: Path) -> bool:
        """
        Check if file should be indexed.

        Args:
            filepath: Path to file

        Returns:
            True if file should be indexed
        """
        # Check if path contains excluded patterns
        for pattern in self.exclude_patterns:
            if pattern in str(filepath):
                return False

        # Check file extension
        if filepath.suffix not in self.include_extensions:
            return False

        # Check file size (skip very large files)
        max_size = config.get('tools.file_operations.max_file_size_mb', 10) * 1024 * 1024
        try:
            if filepath.stat().st_size > max_size:
                logger.debug(f"Skipping large file: {filepath}")
                return False
        except OSError:
            return False

        return True

    def _get_file_hash(self, filepath: Path) -> str:
        """
        Get hash of file contents for change detection.

        Args:
            filepath: Path to file

        Returns:
            MD5 hash of file contents
        """
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash {filepath}: {e}")
            return ""

    def _load_file(self, filepath: Path) -> List[Document]:
        """
        Load and split a single file.

        Args:
            filepath: Path to file

        Returns:
            List of document chunks
        """
        try:
            # Try to load as text
            loader = TextLoader(str(filepath), encoding='utf-8')
            documents = loader.load()

            # Add metadata
            relative_path = str(filepath.relative_to(self.workspace_dir))
            for doc in documents:
                doc.metadata.update({
                    'file_path': relative_path,
                    'file_name': filepath.name,
                    'file_type': filepath.suffix,
                    'full_path': str(filepath)
                })

            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )

            chunks = text_splitter.split_documents(documents)
            logger.debug(f"Loaded {filepath.name}: {len(chunks)} chunks")

            return chunks

        except Exception as e:
            logger.warning(f"Failed to load {filepath}: {e}")
            return []

    def index_workspace(self, force_reindex: bool = False) -> int:
        """
        Index all files in workspace.

        Args:
            force_reindex: Force re-indexing even if files haven't changed

        Returns:
            Number of files indexed
        """
        logger.info(f"🔍 Indexing workspace: {self.workspace_dir}")

        # Ensure nomic-embed-text is downloaded
        self._ensure_embedding_model()

        # Find all indexable files
        all_files = []
        for filepath in self.workspace_dir.rglob('*'):
            if filepath.is_file() and self._should_index_file(filepath):
                all_files.append(filepath)

        logger.info(f"Found {len(all_files)} indexable files")

        # Check which files need indexing
        documents = []
        indexed_count = 0

        for filepath in all_files:
            file_hash = self._get_file_hash(filepath)
            relative_path = str(filepath.relative_to(self.workspace_dir))

            # Skip if already indexed and unchanged
            if not force_reindex and relative_path in self.indexed_files:
                if self.indexed_files[relative_path] == file_hash:
                    continue

            # Load and chunk file
            chunks = self._load_file(filepath)
            if chunks:
                documents.extend(chunks)
                self.indexed_files[relative_path] = file_hash
                indexed_count += 1

        if documents:
            logger.info(f"Indexing {indexed_count} new/changed files ({len(documents)} chunks)")

            # Create or update vector store
            embeddings = self._get_embeddings()

            if self.vectorstore is None:
                # Create new vectorstore
                self.index_dir.mkdir(exist_ok=True)
                self.vectorstore = Chroma.from_documents(
                    documents=documents,
                    embedding=embeddings,
                    persist_directory=str(self.index_dir),
                    collection_name="workspace"
                )
            else:
                # Add to existing vectorstore
                self.vectorstore.add_documents(documents)

            logger.info(f"✓ Indexed {indexed_count} files")
        else:
            # Load existing index if available
            if self.vectorstore is None and self.index_dir.exists():
                logger.info("Loading existing index...")
                embeddings = self._get_embeddings()
                self.vectorstore = Chroma(
                    persist_directory=str(self.index_dir),
                    embedding_function=embeddings,
                    collection_name="workspace"
                )
            logger.info("No new files to index")

        return indexed_count

    def _ensure_embedding_model(self):
        """Ensure nomic-embed-text model is downloaded."""
        try:
            import subprocess
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if 'nomic-embed-text' not in result.stdout:
                logger.info("Downloading nomic-embed-text model...")
                subprocess.run(
                    ['ollama', 'pull', 'nomic-embed-text'],
                    timeout=300
                )
                logger.info("✓ nomic-embed-text downloaded")
        except Exception as e:
            logger.warning(f"Could not check/download embedding model: {e}")

    def search(
        self,
        query: str,
        k: int = 5,
        filter_by_type: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        """
        Semantic search in workspace files.

        Args:
            query: Search query
            k: Number of results to return
            filter_by_type: Optional file extension filter (e.g., '.py')

        Returns:
            List of (document, score) tuples
        """
        if self.vectorstore is None:
            logger.warning("Vectorstore not initialized, indexing now...")
            self.index_workspace()

            if self.vectorstore is None:
                logger.error("Failed to initialize vectorstore")
                return []

        try:
            # Build filter if needed
            filter_dict = None
            if filter_by_type:
                filter_dict = {"file_type": filter_by_type}

            # Perform similarity search
            results = self.vectorstore.similarity_search_with_score(
                query,
                k=k,
                filter=filter_dict
            )

            logger.debug(f"Search '{query}' found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_file_summary(self) -> str:
        """
        Get summary of indexed workspace files.

        Returns:
            Summary string
        """
        if not self.indexed_files:
            return "Workspace not yet indexed."

        # Count by file type
        type_counts = {}
        for filepath in self.indexed_files.keys():
            ext = Path(filepath).suffix or '.txt'
            type_counts[ext] = type_counts.get(ext, 0) + 1

        summary = f"Indexed {len(self.indexed_files)} files:\n"
        for ext, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            summary += f"  {ext}: {count}\n"

        return summary.strip()

    def get_file_tree(self, max_depth: int = 3) -> str:
        """
        Get file tree of workspace.

        Args:
            max_depth: Maximum directory depth

        Returns:
            Tree structure as string
        """
        def build_tree(path: Path, prefix: str = "", depth: int = 0) -> str:
            if depth > max_depth:
                return ""

            items = []
            try:
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

                for i, entry in enumerate(entries):
                    # Skip excluded patterns
                    if any(pattern in str(entry) for pattern in self.exclude_patterns):
                        continue

                    is_last = i == len(entries) - 1
                    connector = "└── " if is_last else "├── "

                    if entry.is_dir():
                        items.append(f"{prefix}{connector}{entry.name}/")
                        if depth < max_depth:
                            extension = "    " if is_last else "│   "
                            items.append(build_tree(entry, prefix + extension, depth + 1))
                    elif self._should_index_file(entry):
                        items.append(f"{prefix}{connector}{entry.name}")

            except PermissionError:
                pass

            return "\n".join(filter(None, items))

        tree = f"{self.workspace_dir.name}/\n"
        tree += build_tree(self.workspace_dir)
        return tree


# Global instance
_workspace_rag: Optional[WorkspaceRAG] = None


def get_workspace_rag() -> WorkspaceRAG:
    """Get or create global workspace RAG instance."""
    global _workspace_rag
    if _workspace_rag is None:
        _workspace_rag = WorkspaceRAG()
    return _workspace_rag
