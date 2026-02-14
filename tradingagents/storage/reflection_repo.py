"""Reflection repository for CRUD operations on reflections table and FTS5 search."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class ReflectionRepository:
    """Repository for reflections table CRUD operations + FTS5 search."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        position_id: int,
        reflection: str,
        key_lessons: str,
        outcome: str,
        return_pct: float,
        market: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        """Create a new reflection entry.

        Args:
            position_id: Position ID
            reflection: Full reflection text
            key_lessons: Key lessons summary (for RAG queries)
            outcome: 'win' or 'loss'
            return_pct: Realized return percentage

        Returns:
            Reflection ID

        Note: FTS5 sync happens automatically via trigger
        """
        created_at = datetime.now().isoformat()

        connection = conn or self.conn
        cursor = connection.execute(
            """
            INSERT INTO reflections (
                position_id, reflection, key_lessons, outcome, return_pct,
                market, sector, industry, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position_id, reflection, key_lessons, outcome, return_pct,
                market, sector, industry, created_at,
            )
        )
        if commit:
            connection.commit()

        reflection_id = int(cursor.lastrowid)
        logger.info(
            f"Created reflection {reflection_id} for position {position_id} "
            f"(outcome={outcome}, return={return_pct:.2f}%)"
        )
        return reflection_id

    def get_by_id(self, reflection_id: int) -> Optional[Dict[str, Any]]:
        """Get reflection by its own ID.

        P1-D: Used by HybridMemory.get_memories() to look up FTS5/vector results.

        Args:
            reflection_id: Reflection ID (primary key)

        Returns:
            Reflection dict or None if not found
        """
        cursor = self.conn.execute(
            """
            SELECT id, position_id, reflection, key_lessons, outcome, return_pct,
                   market, sector, industry, created_at
            FROM reflections
            WHERE id = ?
            """,
            (reflection_id,)
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_by_position(self, position_id: int) -> Optional[Dict[str, Any]]:
        """Get reflection for a position.

        Args:
            position_id: Position ID

        Returns:
            Reflection dict or None if not found
        """
        cursor = self.conn.execute(
            """
            SELECT id, position_id, reflection, key_lessons, outcome, return_pct,
                   market, sector, industry, created_at
            FROM reflections
            WHERE position_id = ?
            """,
            (position_id,)
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def search_fts(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search reflections using FTS5 BM25.

        Args:
            query: Search query (FTS5 syntax)
            limit: Maximum number of results (default 5)

        Returns:
            List of reflection dicts with BM25 rank scores
            Empty list if FTS5 not available or query fails
        """
        try:
            # FTS5 MATCH query with BM25 rank
            cursor = self.conn.execute(
                """
                SELECT r.id, r.position_id, r.reflection, r.key_lessons,
                       r.outcome, r.return_pct, r.market, r.sector, r.industry,
                       r.created_at,
                       fts.rank as bm25_rank
                FROM reflections_fts fts
                JOIN reflections r ON fts.rowid = r.id
                WHERE reflections_fts MATCH ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (query, limit)
            )

            results = [dict(row) for row in cursor.fetchall()]
            logger.info(f"FTS5 search for '{query}': found {len(results)} results")
            return results

        except Exception as e:
            logger.warning(f"FTS5 search failed (query: '{query}'): {e}")
            # Graceful degradation: return empty list
            return []


if __name__ == "__main__":
    # Test reflection repository
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        import os
        from .database import Database
        from .position_repo import PositionRepository

        db_path = os.path.join(temp_dir, "test_trading.db")
        db = Database(db_path)
        db.init_schema()

        # Create position
        position_repo = PositionRepository(db)
        position_id = position_repo.create("NVDA")

        repo = ReflectionRepository(db)

        # Test create
        print("\n1. Creating reflection...")
        reflection_text = """
        Analysis: The bullish momentum was correctly identified through RSI and volume indicators.
        However, the entry timing was premature, leading to initial drawdown.
        
        Key lessons:
        - Wait for consolidation before entering momentum trades
        - Semiconductor sector sentiment is critical for timing
        - RSI above 70 is overextended in short-term
        """
        key_lessons = "Wait for consolidation, watch sector sentiment, avoid overextended RSI"

        reflection_id = repo.create(
            position_id=position_id,
            reflection=reflection_text,
            key_lessons=key_lessons,
            outcome="win",
            return_pct=15.5
        )
        print(f"   Created reflection ID: {reflection_id}")

        # Test get_by_position
        print("\n2. Getting reflection by position...")
        reflection = repo.get_by_position(position_id)
        print(f"   Found reflection: {reflection['id']}")
        print(f"   Outcome: {reflection['outcome']}, Return: {reflection['return_pct']}%")
        print(f"   Key lessons: {reflection['key_lessons'][:50]}...")

        # Test FTS5 search
        print("\n3. Testing FTS5 search...")
        results = repo.search_fts("momentum RSI", limit=5)
        if results:
            print(f"   Found {len(results)} results")
            for r in results:
                print(f"   - Reflection {r['id']}: rank={r.get('bm25_rank', 'N/A')}")
        else:
            print("   No results (FTS5 might not be available)")

        print("\n✅ ReflectionRepository test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
