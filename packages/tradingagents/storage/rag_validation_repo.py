"""Repository for rag_validation_results table."""

from datetime import datetime
from typing import Any, Dict, List

from .database import Database


class RAGValidationRepository:
    """CRUD and summary helpers for rag_validation_results."""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        retrospective_id: int,
        reflection_id: int,
        verdict: str,
        justification: str,
        score_delta: int,
    ) -> int:
        connection = self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO rag_validation_results (
                retrospective_id, reflection_id, verdict, justification, score_delta, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (retrospective_id, reflection_id) DO UPDATE SET
                verdict = EXCLUDED.verdict,
                justification = EXCLUDED.justification,
                score_delta = EXCLUDED.score_delta
            RETURNING id
            """,
            (
                retrospective_id,
                reflection_id,
                verdict,
                justification,
                int(score_delta),
                datetime.now().isoformat(),
            ),
        )
        connection.commit()
        row = cursor.fetchone()
        return int(row["id"]) if row else 0

    def exists(self, retrospective_id: int, reflection_id: int) -> bool:
        row = self.db.get_connection().execute(
            """
            SELECT 1
            FROM rag_validation_results
            WHERE retrospective_id = %s AND reflection_id = %s
            LIMIT 1
            """,
            (retrospective_id, reflection_id),
        ).fetchone()
        return row is not None

    def list_by_retrospective(self, retrospective_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT rvr.id, rvr.retrospective_id, rvr.reflection_id, rvr.verdict,
                   rvr.justification, rvr.score_delta, rvr.created_at,
                   p.ticker
            FROM rag_validation_results rvr
            JOIN reflections r ON r.id = rvr.reflection_id
            JOIN positions p ON p.id = r.position_id
            WHERE rvr.retrospective_id = %s
            ORDER BY rvr.id DESC
            """,
            (retrospective_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_summary(self, cursor: int | None = None, limit: int = 10) -> List[Dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if cursor:
            where = "WHERE ra.id < %s"
            params.append(cursor)

        params.append(limit)
        rows = self.db.get_connection().execute(
            f"""
            SELECT ra.id AS retrospective_id,
                   ra.ticker,
                   ra.position_sequence,
                   COUNT(rvr.id) AS evaluated_count,
                   COUNT(*) FILTER (WHERE rvr.verdict = 'reflected') AS reflected_count,
                   COUNT(*) FILTER (WHERE rvr.verdict = 'not_reflected') AS not_reflected_count,
                   COUNT(*) FILTER (WHERE rvr.verdict = 'ambiguous') AS ambiguous_count,
                   MAX(rvr.created_at) AS created_at
            FROM retrospective_analyses ra
            LEFT JOIN rag_validation_results rvr
              ON rvr.retrospective_id = ra.id
            {where}
            GROUP BY ra.id, ra.ticker, ra.position_sequence
            HAVING COUNT(rvr.id) > 0
            ORDER BY ra.id DESC
            LIMIT %s
            """,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]
