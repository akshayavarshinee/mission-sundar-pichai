"""Arize integration package.

Three responsibilities, mapped to the three places Phoenix is load-bearing:

    tracing.py     — OTel → Phoenix span emission (passive observability)
    mcp_client.py  — active runtime access to Phoenix via @arizeai/phoenix-mcp
    drift.py       — pass-rate monitor over promoted lessons (added in Phase 8)
"""
