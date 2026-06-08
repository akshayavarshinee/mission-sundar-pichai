"""A tiny async pub/sub event bus for the live dashboard (SSE).

Publishers (the service) push JSON-serializable events; subscribers (SSE
connections) each get their own queue. History is retained so a newly-connected
dashboard can replay the demo so far.
"""

from __future__ import annotations

import asyncio
from collections import deque

from clearport.schemas import utcnow


class EventBus:
    def __init__(self, history: int = 200) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._history: deque[dict] = deque(maxlen=history)

    def publish(self, event_type: str, data: dict) -> None:
        event = {"type": event_type, "ts": utcnow().isoformat(), "data": data}
        self._history.append(event)
        for queue in list(self._subscribers):
            queue.put_nowait(event)

    def history(self) -> list[dict]:
        return list(self._history)

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
