"""Hybrid RAG Memory using BM25 + Vector Search with RRF Fusion.

This module provides a memory system that combines:
- BM25 lexical search (via rank-bm25) for keyword matching
- Vector search (via ChromaDB with built-in ONNX embedding) for semantic matching
- RRF (Reciprocal Rank Fusion) for combining results from both retrievers

Storage:
- JSONL file: Source of truth for BM25 corpus (append-only)
- ChromaDB: Derived vector index (can be rebuilt from JSONL)
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

from rank_bm25 import BM25Okapi
import re

logger = logging.getLogger(__name__)


class HybridMemory:
    """Memory system combining BM25 lexical search and ChromaDB vector search."""

    def __init__(self, name: str, config: dict = None):
        """Initialize the hybrid memory system.

        Args:
            name: Name identifier for this memory instance (e.g., 'bull_memory')
            config: Configuration dict containing memory_dir path
        """
        self.name = name
        self.config = config or {}

        # Get memory directory from config or use default
        project_dir = self.config.get("project_dir", os.path.abspath("."))
        memory_dir = self.config.get(
            "memory_dir",
            os.path.join(project_dir, "memory", "data")
        )

        # Ensure memory directory exists
        os.makedirs(memory_dir, exist_ok=True)

        # JSONL file path (source of truth)
        self.jsonl_path = os.path.join(memory_dir, f"{name}.jsonl")

        # ChromaDB path (derived data)
        self.chroma_path = os.path.join(memory_dir, "chroma", name)

        # BM25 index state
        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.metadata_list: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None

        # ChromaDB state (lazy initialization)
        self.chroma_client = None
        self.chroma_collection = None
        self.chroma_available = False

        # Query tracking flag for bootstrap tagging (FR-019)
        self.last_query_had_results = False

        # Load existing corpus from JSONL
        self._load_corpus()

        # BM25 index rebuild
        self._rebuild_bm25()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing.

        Simple whitespace + punctuation tokenization with lowercasing.
        Copied from existing memory.py implementation.
        """
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _rebuild_bm25(self):
        """Rebuild the BM25 index after adding documents.

        Copied from existing memory.py implementation.
        """
        if self.documents:
            tokenized_docs = [self._tokenize(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs)
        else:
            self.bm25 = None

    def _load_corpus(self):
        """Load corpus from JSONL file (source of truth).

        Graceful degradation: Skip corrupted lines with warning.
        """
        if not os.path.exists(self.jsonl_path):
            logger.info(f"No existing corpus found at {self.jsonl_path}, starting fresh")
            return

        try:
            with open(self.jsonl_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        situation = entry.get("situation", "")
                        recommendation = entry.get("recommendation", "")
                        metadata = entry.get("metadata", {})

                        if situation and recommendation:
                            self.documents.append(situation)
                            self.recommendations.append(recommendation)
                            self.metadata_list.append(metadata)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Skipping corrupted line {line_num} in {self.jsonl_path}: {e}"
                        )
                        continue

            logger.info(
                f"Loaded {len(self.documents)} entries from {self.jsonl_path}"
            )
        except Exception as e:
            logger.error(f"Error loading corpus from {self.jsonl_path}: {e}")

    def _save_entry(
        self,
        situation: str,
        recommendation: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Append a single entry to JSONL file (append-only).

        Args:
            situation: Market situation text
            recommendation: LLM reflection/advice
            metadata: Optional metadata dict (ticker, return_pct, has_memory, etc.)
        """
        entry = {
            "situation": situation,
            "recommendation": recommendation,
            "metadata": metadata or {},
        }

        # Ensure created_at timestamp
        if "created_at" not in entry["metadata"]:
            entry["metadata"]["created_at"] = datetime.now().isoformat()

        # Ensure schema_version
        if "schema_version" not in entry["metadata"]:
            entry["metadata"]["schema_version"] = 1

        try:
            with open(self.jsonl_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Error saving entry to {self.jsonl_path}: {e}")

    def _lazy_init_vector(self):
        """Lazy initialization of ChromaDB.

        Only initializes on first get_memories() call.
        Graceful degradation: If ChromaDB fails, fall back to BM25-only mode.
        """
        if self.chroma_client is not None:
            return  # Already initialized

        try:
            import chromadb
            from chromadb.config import Settings

            # PersistentClient with built-in ONNX embedding (all-MiniLM-L6-v2)
            self.chroma_client = chromadb.PersistentClient(
                path=self.chroma_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Get or create collection (default embedding: all-MiniLM-L6-v2)
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name=self.name,
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )

            # Rebuild ChromaDB index from JSONL corpus
            self._rebuild_chroma()

            self.chroma_available = True
            logger.info(f"ChromaDB initialized for {self.name} at {self.chroma_path}")

        except Exception as e:
            logger.warning(
                f"ChromaDB initialization failed for {self.name}, "
                f"falling back to BM25-only mode: {e}"
            )
            self.chroma_available = False

    def _rebuild_chroma(self):
        """Rebuild ChromaDB index from in-memory corpus.

        Called during lazy initialization.
        """
        if not self.chroma_available or not self.chroma_collection:
            return

        if not self.documents:
            logger.info(f"No documents to index for {self.name}")
            return

        try:
            # Check existing count
            existing_count = self.chroma_collection.count()

            # If count matches, assume already synced
            if existing_count == len(self.documents):
                logger.info(
                    f"ChromaDB already synced for {self.name} "
                    f"({existing_count} documents)"
                )
                return

            # Otherwise, rebuild from scratch
            logger.info(
                f"Rebuilding ChromaDB for {self.name}: "
                f"{len(self.documents)} documents"
            )

            # Delete existing collection and recreate
            self.chroma_client.delete_collection(self.name)
            self.chroma_collection = self.chroma_client.create_collection(
                name=self.name,
                metadata={"hnsw:space": "cosine"}
            )

            # Add all documents
            ids = [f"{self.name}_{i}" for i in range(len(self.documents))]
            metadatas = [
                {
                    "recommendation": rec,
                    **meta
                }
                for rec, meta in zip(self.recommendations, self.metadata_list)
            ]

            self.chroma_collection.add(
                documents=self.documents,
                ids=ids,
                metadatas=metadatas
            )

            logger.info(
                f"ChromaDB rebuilt for {self.name}: {len(self.documents)} documents"
            )

        except Exception as e:
            logger.error(f"Error rebuilding ChromaDB for {self.name}: {e}")
            self.chroma_available = False

    def _get_or_create_collection(self):
        """Get or create ChromaDB collection.

        Internal helper (kept for API compatibility with design doc).
        """
        if not self.chroma_available:
            return None
        return self.chroma_collection

    def _rrf_fusion(
        self,
        bm25_results: List[Tuple[int, float]],
        vector_results: List[Tuple[int, float]],
        k: int = 60
    ) -> List[Tuple[int, float]]:
        """RRF (Reciprocal Rank Fusion) score fusion.

        Formula: rrf_score(d) = sum(1 / (k + rank_i(d))) for each retriever

        Args:
            bm25_results: List of (doc_idx, score) from BM25, sorted by score desc
            vector_results: List of (doc_idx, score) from vector search, sorted desc
            k: RRF constant (default 60, standard value from IR literature)

        Returns:
            List of (doc_idx, rrf_score) sorted by rrf_score desc
        """
        rrf_scores: Dict[int, float] = {}

        # BM25 contribution
        for rank, (doc_idx, _) in enumerate(bm25_results, 1):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0.0) + 1.0 / (k + rank)

        # Vector contribution
        for rank, (doc_idx, _) in enumerate(vector_results, 1):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0.0) + 1.0 / (k + rank)

        # Sort by RRF score descending
        sorted_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_results

    def add_situations(
        self,
        situations_and_advice: List[Tuple[str, str]],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add financial situations and their corresponding advice.

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
            metadata: Optional metadata dict to attach to all entries
                     (ticker, return_pct, has_memory, schema_version)
        """
        for situation, recommendation in situations_and_advice:
            # Append to in-memory corpus
            self.documents.append(situation)
            self.recommendations.append(recommendation)
            self.metadata_list.append(metadata or {})

            # Persist to JSONL
            self._save_entry(situation, recommendation, metadata)

            # Add to ChromaDB if available
            if self.chroma_available and self.chroma_collection:
                try:
                    doc_id = f"{self.name}_{len(self.documents) - 1}"
                    self.chroma_collection.add(
                        documents=[situation],
                        ids=[doc_id],
                        metadatas=[{
                            "recommendation": recommendation,
                            **(metadata or {})
                        }]
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to add to ChromaDB for {self.name}, "
                        f"continuing with BM25-only: {e}"
                    )
                    self.chroma_available = False

        # Rebuild BM25 index
        self._rebuild_bm25()

    def get_memories(
        self,
        current_situation: str,
        n_matches: int = 1
    ) -> List[Dict[str, Any]]:
        """Find matching recommendations using Hybrid RAG (BM25 + Vector + RRF).

        Args:
            current_situation: The current financial situation to match against
            n_matches: Number of top matches to return

        Returns:
            List of dicts with matched_situation, recommendation, rrf_score, metadata
            (FR-029: metadata includes outcome, market, sector, industry for RAG labeling)

        Side effect: Sets self.last_query_had_results flag (FR-019)
        """
        # Lazy init ChromaDB on first call
        if not self.chroma_available and self.chroma_client is None:
            self._lazy_init_vector()

        if not self.documents:
            self.last_query_had_results = False
            return []

        # BM25 retrieval
        bm25_results = self._bm25_retrieve(current_situation, n_results=10)

        # Vector retrieval (if available)
        vector_results = []
        if self.chroma_available:
            vector_results = self._vector_retrieve(current_situation, n_results=10)

        # RRF fusion
        if vector_results:
            # Hybrid mode
            fused_results = self._rrf_fusion(bm25_results, vector_results, k=60)
        else:
            # BM25-only fallback
            fused_results = [(idx, score) for idx, score in bm25_results]

        # Build final results (FR-029: include metadata)
        results = []
        for doc_idx, rrf_score in fused_results[:n_matches]:
            results.append({
                "matched_situation": self.documents[doc_idx],
                "recommendation": self.recommendations[doc_idx],
                "rrf_score": rrf_score,
                # Backward compat: also provide similarity_score alias
                "similarity_score": rrf_score,
                # FR-029: Include metadata (outcome, market, sector, industry)
                "metadata": self.metadata_list[doc_idx],
            })

        # Set flag for bootstrap tagging (FR-019)
        self.last_query_had_results = len(results) > 0

        return results

    def _bm25_retrieve(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Tuple[int, float]]:
        """Retrieve top-n documents using BM25.

        Returns:
            List of (doc_idx, score) sorted by score desc
        """
        if not self.documents or self.bm25 is None:
            return []

        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        # Get top-n indices sorted by score (descending)
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:n_results]

        return [(idx, scores[idx]) for idx in top_indices]

    def _vector_retrieve(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Tuple[int, float]]:
        """Retrieve top-n documents using ChromaDB vector search.

        Returns:
            List of (doc_idx, score) sorted by score desc
            Empty list if ChromaDB not available
        """
        if not self.chroma_available or not self.chroma_collection:
            return []

        try:
            # Query ChromaDB (built-in ONNX embedding)
            result = self.chroma_collection.query(
                query_texts=[query],
                n_results=min(n_results, len(self.documents))
            )

            # Extract doc indices from IDs
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]

            # Convert IDs back to doc indices
            # ID format: "{name}_{idx}"
            doc_results = []
            for doc_id, distance in zip(ids, distances):
                try:
                    doc_idx = int(doc_id.split('_')[-1])
                    # Convert distance to similarity (lower distance = higher similarity)
                    # For cosine distance in [0, 2], similarity = 1 - distance/2
                    similarity = 1.0 - (distance / 2.0)
                    doc_results.append((doc_idx, similarity))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse doc_id {doc_id}: {e}")
                    continue

            return doc_results

        except Exception as e:
            logger.error(f"Vector retrieval failed for {self.name}: {e}")
            # Graceful degradation: Disable ChromaDB for future queries
            self.chroma_available = False
            return []

    def clear(self):
        """Clear all stored memories (JSONL + ChromaDB)."""
        # Clear in-memory state
        self.documents = []
        self.recommendations = []
        self.metadata_list = []
        self.bm25 = None

        # Clear JSONL file
        if os.path.exists(self.jsonl_path):
            try:
                os.remove(self.jsonl_path)
                logger.info(f"Cleared JSONL corpus at {self.jsonl_path}")
            except Exception as e:
                logger.error(f"Error clearing JSONL file: {e}")

        # Clear ChromaDB collection
        if self.chroma_available and self.chroma_client:
            try:
                self.chroma_client.delete_collection(self.name)
                logger.info(f"Cleared ChromaDB collection for {self.name}")

                # Recreate empty collection
                self.chroma_collection = self.chroma_client.create_collection(
                    name=self.name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.error(f"Error clearing ChromaDB collection: {e}")


if __name__ == "__main__":
    # Example usage
    print("Testing HybridMemory...")

    # Create test memory
    test_config = {
        "project_dir": os.path.abspath("."),
        "memory_dir": os.path.join(os.path.abspath("."), "test_memory_data")
    }

    memory = HybridMemory("test_memory", test_config)

    # Add example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
    ]

    memory.add_situations(
        example_data,
        metadata={"ticker": "TEST", "has_memory": False}
    )

    # Test query
    query = "Tech sector volatility with rising rates affecting growth stocks"
    results = memory.get_memories(query, n_matches=2)

    print(f"\nQuery: {query}")
    print(f"\nFound {len(results)} matches (had_results={memory.last_query_had_results}):\n")

    for i, rec in enumerate(results, 1):
        print(f"Match {i}:")
        print(f"  RRF Score: {rec['rrf_score']:.4f}")
        print(f"  Situation: {rec['matched_situation'][:80]}...")
        print(f"  Recommendation: {rec['recommendation'][:80]}...")
        print()

    print("HybridMemory test completed!")
