"""Hybrid RAG Memory using SQLite FTS5 + Vector Search with RRF Fusion.

This module provides a memory system that combines:
- SQLite FTS5 lexical search for keyword matching (BM25 내장)
- Vector search (via ChromaDB with built-in ONNX embedding) for semantic matching
- RRF (Reciprocal Rank Fusion) for combining results from both retrievers

Storage:
- SQLite reflections table: Source of truth for reflections (managed by ReflectionRepository)
- SQLite FTS5 virtual table: Derived index for BM25 search (auto-synced via trigger)
- ChromaDB: Vector index for semantic search
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class HybridMemory:
    """Memory system combining SQLite FTS5 lexical search and ChromaDB vector search."""

    def __init__(self, name: str, config: dict = None, db=None):
        """Initialize the hybrid memory system.

        Args:
            name: Name identifier for this memory instance (e.g., 'bull_memory')
                 (kept for backward compatibility, not used in FR-033)
            config: Configuration dict containing database_path and chroma_path
            db: Optional Database instance (if None, creates new connection)
        """
        self.name = name
        self.config = config or {}

        # Get database path from config
        project_dir = self.config.get("project_dir", os.path.abspath("."))
        database_path = self.config.get(
            "database_path",
            os.path.join(project_dir, "memory", "trading.db")
        )

        # Initialize Database connection (if not provided)
        if db is None:
            from tradingagents.storage import Database
            self.db = Database(database_path)
            self.db.init_schema()
            self._owns_db = True
        else:
            self.db = db
            self._owns_db = False

        # Initialize ReflectionRepository for FTS5 search
        from tradingagents.storage import ReflectionRepository
        self.reflection_repo = ReflectionRepository(self.db)

        # ChromaDB path (derived data)
        chroma_path = self.config.get(
            "chroma_path",
            os.path.join(project_dir, "memory", "chroma")
        )
        self.chroma_path = chroma_path

        # ChromaDB state (lazy initialization)
        self.chroma_client = None
        self.chroma_collection = None
        self.chroma_available = False

        # Query tracking flag for bootstrap tagging (FR-019)
        self.last_query_had_results = False

        logger.info(f"HybridMemory initialized (name={name}, FTS5 + ChromaDB)")

    def _lazy_init_vector(self):
        """Lazy initialization of ChromaDB.

        Only initializes on first get_memories() call.
        Graceful degradation: If ChromaDB fails, fall back to FTS5-only mode.
        """
        if self.chroma_client is not None:
            return  # Already initialized

        try:
            import chromadb
            from chromadb.config import Settings

            # Ensure chroma directory exists
            os.makedirs(self.chroma_path, exist_ok=True)

            # PersistentClient with built-in ONNX embedding (all-MiniLM-L6-v2)
            self.chroma_client = chromadb.PersistentClient(
                path=self.chroma_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Get or create collection (default embedding: all-MiniLM-L6-v2)
            # FR-033: Single collection for all reflections (no per-agent split)
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name="reflections",  # Single collection name
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )

            self.chroma_available = True
            logger.info(f"ChromaDB initialized at {self.chroma_path}")

        except Exception as e:
            logger.warning(
                f"ChromaDB initialization failed, "
                f"falling back to FTS5-only mode: {e}"
            )
            self.chroma_available = False

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
        metadata: Optional[Dict[str, Any]] = None,
        reflection_id: Optional[int] = None,
        store_sqlite: bool = True,
    ):
        """Add financial situations and their corresponding advice.

        FR-033: Stores to SQLite reflections + ChromaDB (no JSONL).
        Called by reflect_and_remember (ReflectionAgent only).

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
                                  (kept for API compatibility, but now expects single tuple)
            metadata: Optional metadata dict to attach to all entries
                     Required keys: position_id, outcome, return_pct
        """
        # Extract required fields from metadata
        position_id = metadata.get("position_id") if metadata else None
        if not position_id:
            logger.error("add_situations requires position_id in metadata")
            return

        outcome = metadata.get("outcome") if metadata else None
        return_pct = metadata.get("return_pct", 0.0) if metadata else 0.0
        market = metadata.get("market") if metadata else None
        sector = metadata.get("sector") if metadata else None
        industry = metadata.get("industry") if metadata else None

        if outcome not in {"win", "loss"}:
            logger.error("add_situations requires outcome=win|loss in metadata")
            return
        outcome = str(outcome)

        if not store_sqlite:
            if reflection_id is None:
                logger.error("store_sqlite=False requires reflection_id")
                return
            if len(situations_and_advice) != 1:
                logger.error("store_sqlite=False supports a single situation only")
                return

        for situation, recommendation in situations_and_advice:
            # FR-033: Use ReflectionRepository to store (auto-syncs FTS5 via trigger)
            if store_sqlite:
                try:
                    reflection_id = self.reflection_repo.create(
                        position_id=position_id,
                        reflection=recommendation,  # Full reflection text
                        key_lessons=situation,  # Key lessons for RAG queries
                        outcome=outcome,
                        return_pct=return_pct,
                        market=market,
                        sector=sector,
                        industry=industry,
                    )
                    logger.info(f"Stored reflection {reflection_id} to SQLite + FTS5")

                except Exception as e:
                    logger.error(f"Failed to store reflection to SQLite: {e}")
                    continue

            # Add to ChromaDB if available
            if self.chroma_available and self.chroma_collection:
                try:
                    # Use reflection_id as ChromaDB doc ID
                    doc_id = f"reflection_{reflection_id}"
                    self.chroma_collection.add(
                        documents=[situation],  # Embed key_lessons for semantic search
                        ids=[doc_id],
                        metadatas=[{
                            "reflection_id": reflection_id,
                            "recommendation": recommendation,
                            **(metadata or {})
                        }]
                    )
                    logger.info(f"Added reflection {reflection_id} to ChromaDB")

                except Exception as e:
                    logger.warning(
                        f"Failed to add to ChromaDB (reflection_id={reflection_id}), "
                        f"continuing with FTS5-only: {e}"
                    )
                    self.chroma_available = False

    def get_memories(
        self,
        current_situation: str,
        n_matches: int = 1
    ) -> List[Dict[str, Any]]:
        """Find matching recommendations using Hybrid RAG (FTS5 + Vector + RRF).

        FR-033: Replaces rank_bm25 with SQLite FTS5.

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

        # FTS5 retrieval (BM25)
        fts5_results = self._fts5_retrieve(current_situation, n_results=10)

        # Vector retrieval (if available)
        vector_results = []
        if self.chroma_available:
            vector_results = self._vector_retrieve(current_situation, n_results=10)

        # RRF fusion
        if vector_results and fts5_results:
            # Hybrid mode
            fused_results = self._rrf_fusion(fts5_results, vector_results, k=60)
        elif fts5_results:
            # FTS5-only fallback
            fused_results = [(idx, score) for idx, score in fts5_results]
        elif vector_results:
            # Vector-only fallback (rare case: FTS5 failed but vector worked)
            fused_results = [(idx, score) for idx, score in vector_results]
        else:
            # No results from either
            self.last_query_had_results = False
            return []

        # Build final results (FR-029: include metadata + labels)
        results = []
        for reflection_id, rrf_score in fused_results[:n_matches]:
            # Get reflection from DB
            reflection = self.reflection_repo.get_by_id(reflection_id)
            if not reflection:
                continue

            # FR-029: Add outcome label
            outcome = reflection.get("outcome")
            if outcome == "win":
                outcome_label = "[✅ 성공 사례]"
            elif outcome == "loss":
                outcome_label = "[⚠️ 실패 사례]"
            else:
                outcome_label = "[❓ 미정]"

            results.append({
                "matched_situation": reflection.get("key_lessons", ""),
                "recommendation": reflection.get("reflection", ""),
                "rrf_score": rrf_score,
                # Backward compat: also provide similarity_score alias
                "similarity_score": rrf_score,
                # FR-029: Include metadata with label
                "metadata": {
                    "reflection_id": reflection.get("id"),
                    "position_id": reflection.get("position_id"),
                    "outcome": reflection.get("outcome"),
                    "outcome_label": outcome_label,
                    "return_pct": reflection.get("return_pct"),
                    "market": reflection.get("market"),
                    "sector": reflection.get("sector"),
                    "industry": reflection.get("industry"),
                },
            })

        # Set flag for bootstrap tagging (FR-019)
        self.last_query_had_results = len(results) > 0

        return results

    def _fts5_retrieve(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Tuple[int, float]]:
        """Retrieve top-n reflections using SQLite FTS5 BM25.

        FR-033: Replaces _bm25_retrieve (rank_bm25 removal).

        Returns:
            List of (reflection_id, score) sorted by score desc
            Empty list if FTS5 search fails
        """
        try:
            results_dicts = self.reflection_repo.search_fts(query, limit=n_results)
            # Convert to (id, score) tuples
            # FTS5 rank is negative (lower = better), invert for consistency
            return [(r["id"], -r.get("bm25_rank", 0.0)) for r in results_dicts]

        except Exception as e:
            logger.warning(f"FTS5 search failed (query: '{query}'): {e}")
            return []

    def _vector_retrieve(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Tuple[int, float]]:
        """Retrieve top-n reflections using ChromaDB vector search.

        FR-033: Updated to use reflection_id instead of name_idx format.

        Returns:
            List of (reflection_id, score) sorted by score desc
            Empty list if ChromaDB not available
        """
        if not self.chroma_available or not self.chroma_collection:
            return []

        try:
            # Query ChromaDB (built-in ONNX embedding)
            result = self.chroma_collection.query(
                query_texts=[query],
                n_results=n_results
            )

            # Extract doc IDs and distances
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]

            # Convert IDs back to reflection_id
            # ID format: "reflection_{reflection_id}"
            doc_results = []
            for doc_id, distance in zip(ids, distances):
                try:
                    reflection_id = int(doc_id.split('_')[1])
                    # Convert distance to similarity (lower distance = higher similarity)
                    # For cosine distance in [0, 2], similarity = 1 - distance/2
                    similarity = 1.0 - (distance / 2.0)
                    doc_results.append((reflection_id, similarity))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse doc_id {doc_id}: {e}")
                    continue

            return doc_results

        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            # Graceful degradation: Disable ChromaDB for future queries
            self.chroma_available = False
            return []

    def clear(self):
        """Clear all stored memories (SQLite reflections + ChromaDB).

        WARNING: This will delete ALL reflections in the database.
        """
        # Clear SQLite reflections (requires admin operation)
        logger.warning("clear() is destructive and not recommended. Skipping SQLite delete.")
        # To actually delete: self.db.get_connection().execute("DELETE FROM reflections")

        # Clear ChromaDB collection
        if self.chroma_available and self.chroma_client:
            try:
                self.chroma_client.delete_collection("reflections")
                logger.info("Cleared ChromaDB collection 'reflections'")

                # Recreate empty collection
                self.chroma_collection = self.chroma_client.create_collection(
                    name="reflections",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.error(f"Error clearing ChromaDB collection: {e}")

    def close(self):
        """Close database connection if owned."""
        if self._owns_db and self.db:
            self.db.close()


if __name__ == "__main__":
    # Example usage
    print("Testing HybridMemory with FTS5...")

    # Create test memory
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        test_config = {
            "project_dir": temp_dir,
            "database_path": os.path.join(temp_dir, "test_trading.db"),
            "chroma_path": os.path.join(temp_dir, "test_chroma")
        }

        memory = HybridMemory("test_memory", test_config)

        # Add example data (requires position_id)
        # NOTE: In real usage, position_id comes from PositionRepository
        print("\nAdding test reflection...")
        example_data = [
            (
                "Wait for consolidation before entering momentum trades. Watch sector sentiment.",
                "Analysis: The bullish momentum was correctly identified through RSI...",
            )
        ]

        # Mock position_id for testing
        from tradingagents.storage import PositionRepository
        position_repo = PositionRepository(memory.db)
        position_id = position_repo.create("TEST")

        memory.add_situations(
            example_data,
            metadata={
                "position_id": position_id,
                "outcome": "win",
                "return_pct": 15.5
            }
        )

        # Test query
        query = "momentum sector consolidation"
        results = memory.get_memories(query, n_matches=2)

        print(f"\nQuery: {query}")
        print(f"\nFound {len(results)} matches (had_results={memory.last_query_had_results}):\n")

        for i, rec in enumerate(results, 1):
            print(f"Match {i}:")
            print(f"  RRF Score: {rec['rrf_score']:.4f}")
            print(f"  Situation: {rec['matched_situation'][:80]}...")
            print(f"  Recommendation: {rec['recommendation'][:80]}...")
            print(f"  Metadata: {rec['metadata']}")
            print()

        print("✅ HybridMemory FTS5 test completed!")

        memory.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")

