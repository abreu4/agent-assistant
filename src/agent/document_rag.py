"""RAG system for CV, cover letters, and job application documents."""
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

logger = get_logger("document_rag")


class DocumentRAG:
    """
    RAG system for job application documents (CV, cover letters, etc.).

    Indexes PDF, DOCX, TXT, and MD files in the documents directory,
    providing semantic search capabilities for the agent.
    """

    def __init__(self, documents_dir: Optional[str] = None):
        """
        Initialize document RAG system.

        Args:
            documents_dir: Documents directory to index (default: from config job_agent.documents_path)
        """
        if documents_dir is None:
            documents_dir = config.get('job_agent.documents_path', '~/job_applications/documents')

        self.documents_dir = Path(documents_dir).expanduser()
        self.vectorstore: Optional[Chroma] = None
        self.embeddings = None
        self.indexed_files: Dict[str, str] = {}  # filepath -> hash
        self.index_dir = Path.home() / ".job_agent" / "document_index"

        # File patterns for job documents (PDF and TXT only)
        self.include_extensions = ['.pdf', '.txt', '.md']

        # Patterns to exclude
        self.exclude_patterns = [
            '__pycache__', '.git', '.DS_Store', 'thumbs.db',
            '.tmp', '.temp', '~$'  # Office temp files
        ]

        logger.debug(f"Document RAG initialized for: {self.documents_dir}")

    def _get_embeddings(self):
        """Get or create embeddings model."""
        if self.embeddings is None:
            # Use local Ollama embeddings for privacy
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
                        model="llama3.2:3b",
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
        if filepath.suffix.lower() not in self.include_extensions:
            return False

        # Check file size (skip very large files > 50MB)
        max_size = 50 * 1024 * 1024  # 50MB for documents
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

    def _load_pdf(self, filepath: Path) -> List[Document]:
        """
        Load PDF file.

        Args:
            filepath: Path to PDF file

        Returns:
            List of document chunks
        """
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(filepath))
            text = ""

            # Extract text from all pages
            for page in reader.pages:
                text += page.extract_text() + "\n\n"

            if not text.strip():
                logger.warning(f"No text extracted from PDF: {filepath}")
                return []

            # Create document with metadata
            doc = Document(
                page_content=text,
                metadata={
                    'file_path': str(filepath),
                    'file_name': filepath.name,
                    'file_type': filepath.suffix,
                    'num_pages': len(reader.pages)
                }
            )

            return [doc]

        except ImportError:
            logger.error("pypdf not installed. Install with: pip install pypdf")
            return []
        except Exception as e:
            logger.warning(f"Failed to load PDF {filepath}: {e}")
            return []

    def _load_text(self, filepath: Path) -> List[Document]:
        """
        Load text file (TXT, MD).

        Args:
            filepath: Path to text file

        Returns:
            List of document chunks
        """
        try:
            loader = TextLoader(str(filepath), encoding='utf-8')
            documents = loader.load()

            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    'file_path': str(filepath),
                    'file_name': filepath.name,
                    'file_type': filepath.suffix
                })

            return documents

        except Exception as e:
            logger.warning(f"Failed to load text file {filepath}: {e}")
            return []

    def _load_file(self, filepath: Path) -> List[Document]:
        """
        Load a single document file.

        Args:
            filepath: Path to file

        Returns:
            List of document chunks
        """
        ext = filepath.suffix.lower()

        # Route to appropriate loader
        if ext == '.pdf':
            documents = self._load_pdf(filepath)
        elif ext in ['.txt', '.md']:
            documents = self._load_text(filepath)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []

        if not documents:
            return []

        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = text_splitter.split_documents(documents)
        logger.debug(f"Loaded {filepath.name}: {len(chunks)} chunks")

        return chunks

    def index_documents(self, force_reindex: bool = False) -> int:
        """
        Index all documents in documents directory.

        Args:
            force_reindex: Force re-indexing even if files haven't changed

        Returns:
            Number of files indexed
        """
        logger.info(f"🔍 Indexing documents: {self.documents_dir}")

        # Create documents directory if it doesn't exist
        self.documents_dir.mkdir(parents=True, exist_ok=True)

        # Ensure embedding model is available
        self._ensure_embedding_model()

        # Find all indexable files
        all_files = []
        for filepath in self.documents_dir.rglob('*'):
            if filepath.is_file() and self._should_index_file(filepath):
                all_files.append(filepath)

        logger.info(f"Found {len(all_files)} indexable documents")

        if not all_files:
            logger.info("No documents found to index")
            return 0

        # Check which files need indexing
        documents = []
        indexed_count = 0

        for filepath in all_files:
            file_hash = self._get_file_hash(filepath)
            file_key = str(filepath)

            # Skip if already indexed and unchanged
            if not force_reindex and file_key in self.indexed_files:
                if self.indexed_files[file_key] == file_hash:
                    continue

            # Load and chunk file
            chunks = self._load_file(filepath)
            if chunks:
                documents.extend(chunks)
                self.indexed_files[file_key] = file_hash
                indexed_count += 1

        if documents:
            logger.info(f"Indexing {indexed_count} new/changed files ({len(documents)} chunks)")

            # Create or update vector store
            embeddings = self._get_embeddings()

            if self.vectorstore is None:
                # Create new vectorstore
                self.index_dir.mkdir(parents=True, exist_ok=True)
                self.vectorstore = Chroma.from_documents(
                    documents=documents,
                    embedding=embeddings,
                    persist_directory=str(self.index_dir),
                    collection_name="documents"
                )
            else:
                # Add to existing vectorstore
                self.vectorstore.add_documents(documents)

            logger.info(f"✓ Indexed {indexed_count} documents")
        else:
            # Load existing index if available
            if self.vectorstore is None and self.index_dir.exists():
                logger.info("Loading existing index...")
                embeddings = self._get_embeddings()
                self.vectorstore = Chroma(
                    persist_directory=str(self.index_dir),
                    embedding_function=embeddings,
                    collection_name="documents"
                )
            logger.info("No new documents to index")

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
        Semantic search in documents.

        Args:
            query: Search query
            k: Number of results to return
            filter_by_type: Optional file extension filter (e.g., '.pdf')

        Returns:
            List of (document, score) tuples
        """
        if self.vectorstore is None:
            logger.warning("Vectorstore not initialized, indexing now...")
            self.index_documents()

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

    def get_document_summary(self) -> str:
        """
        Get summary of indexed documents.

        Returns:
            Summary string
        """
        if not self.indexed_files:
            return "No documents indexed yet."

        # Count by file type
        type_counts = {}
        for filepath in self.indexed_files.keys():
            ext = Path(filepath).suffix.lower() or '.txt'
            type_counts[ext] = type_counts.get(ext, 0) + 1

        summary = f"Indexed {len(self.indexed_files)} documents:\n"
        for ext, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            summary += f"  {ext}: {count}\n"

        return summary.strip()


# Global instance
_document_rag: Optional[DocumentRAG] = None


def get_document_rag() -> DocumentRAG:
    """Get or create global document RAG instance."""
    global _document_rag
    if _document_rag is None:
        _document_rag = DocumentRAG()
    return _document_rag
