"""HTTP surface (FastAPI) + the application service that drives the loop.

    service.py    — ClearPortService: submit shipments, approve/reject/correct
    store.py      — in-memory run + approval store (offline-friendly)
    events.py     — async event bus for the live dashboard (SSE)
    metrics.py    — the four headline metrics
    main.py       — FastAPI app wiring it together
"""
