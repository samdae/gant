"""Hybrid RAG Memory using Postgres FTS + Vector Search with RRF Fusion.

This module provides a memory system that combines:
- Postgres FTS lexical search for keyword matching
- Vector search (via ChromaDB with built-in ONNX embedding) for semantic matching
- RRF (Reciprocal Rank Fusion) for combining results from both retrievers

Storage:
- Postgres reflections table: Source of truth for reflections (managed by ReflectionRepository)
- ChromaDB: Vector index for semantic search
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class HybridMemory:
    """Memory system combining Postgres FTS lexical search and ChromaDB vector search."""

    def __init__(
        self,
        name: str,
        config: dict = None,
        db=None,
        collection_name: str = "analysis_reflections",
        source_table: Optional[str] = None,
    ):
        """Initialize the hybrid memory system.

        Args:
            name: Name identifier for this memory instance (e.g., 'bull_memory')
                 (kept for backward compatibility, not used in FR-033)
            config: Configuration dict containing database_path and chroma_path
            db: Optional Database instance (if None, creates new connection)
            collection_name: ChromaDB collection name
            source_table: FTS/row lookup table ('reflections' or 'portfolio_reflections')
        """
        self.name = name
        self.config = config or {}
        self.collection_name = collection_name or "analysis_reflections"
        self.source_table = source_table or self._source_table_from_collection(self.collection_name)

        # Get database URL from config
        project_dir = self.config.get("project_dir", os.path.abspath("."))
        database_url = self.config.get("database_path") or os.getenv("SUPABASE_DB_URL", "")

        # Initialize Database connection (if not provided)
        if db is None:
            from tradingagents.storage import Database
            self.db = Database(database_url)
            self.db.init_schema()
            self._owns_db = True
        else:
            self.db = db
            self._owns_db = False

        # Initialize repositories for source tables
        from tradingagents.storage import ReflectionRepository, PortfolioReflectionRepository

        self.reflection_repo = ReflectionRepository(self.db)
        self.portfolio_reflection_repo = PortfolioReflectionRepository(self.db)

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

        logger.info(
            "HybridMemory initialized (name=%s, collection=%s, source_table=%s)",
            name,
            self.collection_name,
            self.source_table,
        )

    @staticmethod
    def _source_table_from_collection(collection_name: str) -> str:
        if str(collection_name or "").strip().lower() == "portfolio_reflections":
            return "portfolio_reflections"
        return "reflections"

    def _lazy_init_vector(self):
        """Lazy initialization of ChromaDB.

        Only initializes on first get_memories() call.
        Graceful degradation: If ChromaDB fails, fall back to FTS-only mode.
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
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )

            self.chroma_available = True
            logger.info(f"ChromaDB initialized at {self.chroma_path}")

        except Exception as e:
            logger.warning(
                f"ChromaDB initialization failed, "
                f"falling back to FTS-only mode: {e}"
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
        if not situations_and_advice:
            return

        metadata = metadata or {}
        position_id = metadata.get("position_id")
        outcome = metadata.get("outcome")
        return_pct = metadata.get("return_pct", 0.0)
        market = metadata.get("market")
        sector = metadata.get("sector")
        industry = metadata.get("industry")

        # Ensure vector client is ready before inserts.
        if not self.chroma_available and self.chroma_client is None:
            self._lazy_init_vector()

        if store_sqlite and self.source_table != "reflections":
            logger.error(
                "store_sqlite=True is only supported for source_table='reflections'"
            )
            return

        if not store_sqlite:
            if reflection_id is None:
                logger.error("store_sqlite=False requires reflection_id")
                return
            if len(situations_and_advice) != 1:
                logger.error("store_sqlite=False supports a single situation only")
                return
        else:
            if not position_id:
                logger.error("add_situations requires position_id in metadata")
                return
            if outcome not in {"win", "loss"}:
                logger.error("add_situations requires outcome=win|loss in metadata")
                return
            outcome = str(outcome)

        for situation, recommendation in situations_and_advice:
            # FR-033: Use ReflectionRepository to store in Postgres
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
                    logger.info(f"Stored reflection {reflection_id} to Postgres + FTS")

                except Exception as e:
                    logger.error(f"Failed to store reflection to Postgres: {e}")
                    continue

            # Add to ChromaDB if available
            if self.chroma_available and self.chroma_collection:
                try:
                    # Use reflection_id as ChromaDB doc ID
                    doc_id = f"reflection_{reflection_id}"
                    metadata_payload = {
                        "reflection_id": reflection_id,
                        "recommendation": recommendation,
                        "source_collection": self.collection_name,
                        **metadata,
                    }
                    self.chroma_collection.add(
                        documents=[situation],  # Embed key_lessons for semantic search
                        ids=[doc_id],
                        metadatas=[metadata_payload],
                    )
                    logger.info(f"Added reflection {reflection_id} to ChromaDB")

                except Exception as e:
                    logger.warning(
                        f"Failed to add to ChromaDB (reflection_id={reflection_id}), "
                        f"continuing with FTS-only: {e}"
                    )
                    self.chroma_available = False

    def add_external_document(
        self,
        document_id: int,
        matched_situation: str,
        recommendation: str,
        collection_name: str,
        source_table: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store externally managed reflection-like document to Chroma collection."""
        if self.chroma_client is None:
            self._lazy_init_vector()
        if self.chroma_client is None:
            return
        metadata = metadata or {}
        try:
            collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            collection.add(
                documents=[matched_situation],
                ids=[f"reflection_{int(document_id)}"],
                metadatas=[
                    {
                        "reflection_id": int(document_id),
                        "recommendation": recommendation,
                        "source_table": source_table,
                        "source_collection": collection_name,
                        **metadata,
                    }
                ],
            )
        except Exception as exc:
            logger.warning("Failed to add external document to ChromaDB: %s", exc)

    def _get_document_by_id(
        self,
        reflection_id: int,
        source_table: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        table = source_table or self.source_table
        if table == "portfolio_reflections":
            row = self.portfolio_reflection_repo.get_by_id(reflection_id)
            if not row:
                return None
            return {
                "id": row.get("id"),
                "position_id": None,
                "reflection": row.get("reflection_content", ""),
                "key_lessons": row.get("key_lessons", ""),
                "outcome": None,
                "return_pct": row.get("total_return_pct"),
                "market": None,
                "sector": None,
                "industry": None,
                "usefulness_score": 50.0,
                "created_at": row.get("created_at"),
            }
        return self.reflection_repo.get_by_id(reflection_id)

    def _search_portfolio_fts(self, query: str, limit: int = 10) -> List[Tuple[int, float]]:
        try:
            rows = self.db.get_connection().execute(
                """
                SELECT id,
                       ts_rank_cd(
                           to_tsvector('simple', coalesce(reflection_content, '') || ' ' || coalesce(key_lessons, '')),
                           plainto_tsquery('simple', %s)
                       ) AS ts_rank
                FROM portfolio_reflections
                WHERE to_tsvector('simple', coalesce(reflection_content, '') || ' ' || coalesce(key_lessons, ''))
                      @@ plainto_tsquery('simple', %s)
                ORDER BY ts_rank DESC
                LIMIT %s
                """,
                (query, query, limit),
            ).fetchall()
            return [(int(r["id"]), float(r.get("ts_rank") or 0.0)) for r in rows]
        except Exception as exc:
            logger.warning("Portfolio FTS search failed: %s", exc)
            return []

    def get_memories(
        self,
        current_situation: str,
        n_matches: int = 1
    ) -> List[Dict[str, Any]]:
        """Find matching recommendations using Hybrid RAG (FTS + Vector + RRF).

        FR-033: Replaces rank_bm25 with Postgres FTS.

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

        # FR-052: RRF candidates are fixed to top-3 per retriever.
        fts_results = self._fts_retrieve(current_situation, n_results=3)

        # Vector retrieval (if available)
        vector_results = []
        if self.chroma_available:
            vector_results = self._vector_retrieve(current_situation, n_results=3)

        # RRF fusion
        if vector_results and fts_results:
            # Hybrid mode
            fused_results = self._rrf_fusion(fts_results, vector_results, k=60)
        elif fts_results:
            # FTS-only fallback
            fused_results = [(idx, score) for idx, score in fts_results]
        elif vector_results:
            # Vector-only fallback (rare case: FTS failed but vector worked)
            fused_results = [(idx, score) for idx, score in vector_results]
        else:
            # No results from either
            self.last_query_had_results = False
            return []

        # FR-052: Keep top-3 by relevance (RRF), then filter/sort by usefulness.
        fused_results = fused_results[:3]
        filtered_results, usefulness_map = self._apply_usefulness_filter(
            fused_results,
            top_k=n_matches,
        )
        if not filtered_results:
            self.last_query_had_results = False
            return []

        # Build final results (FR-029: include metadata + labels)
        results = []
        for reflection_id, rrf_score in filtered_results:
            # Get reflection from DB
            reflection = self._get_document_by_id(reflection_id)
            if not reflection:
                continue

            # FR-029: Add outcome label
            outcome = reflection.get("outcome")
            if outcome == "win":
                outcome_label = "[✅ 성공 사례]"
            elif outcome == "loss":
                outcome_label = "[⚠️ 실패 사례]"
            elif self.source_table == "portfolio_reflections":
                outcome_label = "[📌 포트폴리오 사례]"
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
                    "usefulness_score": usefulness_map.get(
                        int(reflection.get("id")), 50.0
                    ),
                    "source_collection": self.collection_name,
                },
            })

        # Set flag for bootstrap tagging (FR-019)
        self.last_query_had_results = len(results) > 0

        return results

    def _apply_usefulness_filter(
        self,
        fused_results: List[Tuple[int, float]],
        top_k: int,
    ) -> tuple:
        """Filter by usefulness and return (top-k results, usefulness_map).

        Returns:
            Tuple of (filtered_results, usefulness_map) to avoid duplicate DB queries.
        """
        if not fused_results:
            return [], {}

        reflection_ids = [doc_id for doc_id, _ in fused_results]
        if self.source_table == "reflections":
            usefulness_map = self.reflection_repo.get_usefulness_scores(reflection_ids)
        else:
            usefulness_map = {int(reflection_id): 50.0 for reflection_id in reflection_ids}

        filtered = []
        for reflection_id, rrf_score in fused_results:
            usefulness = usefulness_map.get(reflection_id, 50.0)
            if self.source_table == "reflections" and usefulness < 40:
                continue
            filtered.append((reflection_id, rrf_score, usefulness))

        filtered.sort(key=lambda x: (x[2], x[1]), reverse=True)
        limit = max(int(top_k), 1)
        return [(reflection_id, score) for reflection_id, score, _ in filtered[:limit]], usefulness_map

    def _fts_retrieve(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Tuple[int, float]]:
        """Retrieve top-n reflections using Postgres FTS.

        FR-033: Replaces _bm25_retrieve (rank_bm25 removal).

        Returns:
            List of (reflection_id, score) sorted by score desc
            Empty list if FTS search fails
        """
        try:
            if self.source_table == "portfolio_reflections":
                return self._search_portfolio_fts(query, limit=n_results)
            results_dicts = self.reflection_repo.search_fts(query, limit=n_results)
            return [(r["id"], float(r.get("ts_rank", 0.0))) for r in results_dicts]

        except Exception as e:
            logger.warning(f"FTS search failed (query: '{query}'): {e}")
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

    def search_semantic(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Semantic-only reflection search using ChromaDB."""
        if not self.chroma_available and self.chroma_client is None:
            self._lazy_init_vector()
        if not self.chroma_available:
            raise RuntimeError("ChromaDB is not available")

        vector_results = self._vector_retrieve(query, n_results=limit)
        results: List[Dict[str, Any]] = []
        for reflection_id, similarity in vector_results:
            reflection = self._get_document_by_id(reflection_id)
            if not reflection:
                continue
            results.append(
                {
                    "id": reflection.get("id"),
                    "position_id": reflection.get("position_id"),
                    "matched_situation": reflection.get("key_lessons", ""),
                    "reflection": reflection.get("reflection", ""),
                    "outcome": reflection.get("outcome"),
                    "return_pct": reflection.get("return_pct"),
                    "usefulness_score": reflection.get("usefulness_score", 50.0),
                    "semantic_score": similarity,
                    "created_at": reflection.get("created_at"),
                    "source_collection": self.collection_name,
                }
            )
        return results

    def _vector_retrieve_from_collection(
        self,
        query: str,
        n_results: int,
        collection_name: str,
    ) -> List[Tuple[int, float]]:
        if self.chroma_client is None:
            self._lazy_init_vector()
        if self.chroma_client is None:
            return []
        try:
            collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            result = collection.query(query_texts=[query], n_results=n_results)
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]
            parsed: List[Tuple[int, float]] = []
            for doc_id, distance in zip(ids, distances):
                try:
                    reflection_id = int(str(doc_id).split("_")[1])
                    similarity = 1.0 - (float(distance) / 2.0)
                    parsed.append((reflection_id, similarity))
                except Exception:
                    continue
            return parsed
        except Exception as exc:
            logger.warning(
                "Vector retrieval failed for collection=%s: %s",
                collection_name,
                exc,
            )
            return []

    def get_memories_cross(
        self,
        query: str,
        primary_collection: str,
        secondary_collection: str,
        primary_k: int,
        secondary_k: int,
    ) -> List[Dict[str, Any]]:
        """Cross-collection retrieval for portfolio mode."""
        primary = self._vector_retrieve_from_collection(
            query=query,
            n_results=max(int(primary_k), 0),
            collection_name=primary_collection,
        )
        secondary = self._vector_retrieve_from_collection(
            query=query,
            n_results=max(int(secondary_k), 0),
            collection_name=secondary_collection,
        )

        candidates = []
        for source_collection, rows in (
            (primary_collection, primary),
            (secondary_collection, secondary),
        ):
            source_table = self._source_table_from_collection(source_collection)
            for reflection_id, score in rows:
                doc = self._get_document_by_id(reflection_id, source_table=source_table)
                if not doc:
                    continue
                outcome = doc.get("outcome")
                if outcome == "win":
                    outcome_label = "[✅ 성공 사례]"
                elif outcome == "loss":
                    outcome_label = "[⚠️ 실패 사례]"
                elif source_table == "portfolio_reflections":
                    outcome_label = "[📌 포트폴리오 사례]"
                else:
                    outcome_label = "[❓ 미정]"

                candidates.append(
                    {
                        "matched_situation": doc.get("key_lessons", ""),
                        "recommendation": doc.get("reflection", ""),
                        "rrf_score": score,
                        "similarity_score": score,
                        "metadata": {
                            "reflection_id": doc.get("id"),
                            "position_id": doc.get("position_id"),
                            "outcome": doc.get("outcome"),
                            "outcome_label": outcome_label,
                            "return_pct": doc.get("return_pct"),
                            "market": doc.get("market"),
                            "sector": doc.get("sector"),
                            "industry": doc.get("industry"),
                            "usefulness_score": doc.get("usefulness_score", 50.0),
                            "source_collection": source_collection,
                        },
                    }
                )

        # Deduplicate by reflection_id + source_collection keeping best score.
        best: Dict[Tuple[Any, str], Dict[str, Any]] = {}
        for item in candidates:
            key = (
                item["metadata"].get("reflection_id"),
                str(item["metadata"].get("source_collection")),
            )
            prev = best.get(key)
            if prev is None or float(item.get("rrf_score", 0.0)) > float(prev.get("rrf_score", 0.0)):
                best[key] = item

        merged = sorted(best.values(), key=lambda x: float(x.get("rrf_score", 0.0)), reverse=True)
        return merged

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
                self.chroma_client.delete_collection(self.collection_name)
                logger.info("Cleared ChromaDB collection '%s'", self.collection_name)

                # Recreate empty collection
                self.chroma_collection = self.chroma_client.create_collection(
                    name=self.collection_name,
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
    print("Testing HybridMemory with FTS...")

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

        print("✅ HybridMemory FTS test completed!")

        memory.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")

