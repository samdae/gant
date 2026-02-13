"""FastAPI web backend for TradingAgents.

Provides REST API + WebSocket for:
- Schedule management (CRUD)
- Trade data queries
- Archive queries
- Analysis queue status
- Health check
- RAG search

Authentication:
- READ (GET): Public
- WRITE (POST/PUT/DELETE): Bearer token required
"""
