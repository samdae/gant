"""Latest published forecast per instrument, including instruments outside the recent page."""


def published_tickers(conn):
    rows = conn.execute("""
        WITH latest AS (
            SELECT DISTINCT ON (c.ticker) c.id, c.ticker, c.data_session
            FROM lab_cases c
            WHERE EXISTS (
                SELECT 1 FROM lab_arms a WHERE a.case_id = c.id
                  AND a.status = 'published' AND a.published_at <= statement_timestamp()
                  AND a.published_at < c.entry_at)
            ORDER BY c.ticker, c.data_session DESC, c.id DESC
        )
        SELECT l.id, l.ticker, l.data_session, c.snapshot->>'market' AS market,
               s.probability
        FROM latest l JOIN lab_cases c ON c.id = l.id
        LEFT JOIN lab_arms s ON s.case_id = l.id AND s.method = 'single'
          AND s.status = 'published' AND s.published_at <= statement_timestamp()
          AND s.published_at < c.entry_at
        ORDER BY l.data_session DESC, l.id DESC
    """).fetchall()
    return [
        {
            "id": row["id"], "ticker": row["ticker"], "market": row["market"],
            "data_session": row["data_session"].isoformat(),
            "forecast_probabilities": {"single": row["probability"]} if row["probability"] is not None else {},
        }
        for row in rows
    ]
