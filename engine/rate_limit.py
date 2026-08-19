"""
Minimal in-memory rate limiter for the public, unauthenticated chat
endpoints (/session/start, /session/message). Without this, nothing stops
a client from hammering /session/message - each call costs a real LLM API
request, so this is a direct cost-abuse vector, not just a load concern.

Deliberately simple: a fixed-window counter per client IP, in a process-
local dict behind a lock. Good enough for a single-instance self-hosted
deployment (the stated target - see DESIGN.md, 5-20 person teams). It
does NOT survive a restart and does NOT coordinate across multiple
instances - if you scale out to several replicas, replace this with a
shared store (Redis, etc.) keyed the same way. That's a deliberate scope
cut, not an oversight: building a distributed limiter for a single-file
SQLite-based self-hosted tool would be solving a problem this project's
target user doesn't have yet.
"""
import os
import threading
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = int(os.getenv("TACKETY_RATE_LIMIT_PER_MINUTE", "30"))

_lock = threading.Lock()
_hits: Dict[str, List[float]] = defaultdict(list)


def _client_key(request: Request) -> str:
    # Trusts the direct connecting peer, not X-Forwarded-For - this is a
    # simple abuse guard for a self-hosted single instance, not a proxy-
    # aware production rate limiter.
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request):
    """FastAPI dependency: raises 429 once a client exceeds
    MAX_REQUESTS_PER_WINDOW requests in the trailing WINDOW_SECONDS."""
    key = _client_key(request)
    now = time.monotonic()
    cutoff = now - WINDOW_SECONDS

    with _lock:
        hits = _hits[key]
        # Drop expired hits so this dict doesn't grow unboundedly under
        # long-running processes with many distinct clients.
        while hits and hits[0] < cutoff:
            hits.pop(0)

        if len(hits) >= MAX_REQUESTS_PER_WINDOW:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {MAX_REQUESTS_PER_WINDOW} requests per {WINDOW_SECONDS}s."
            )

        hits.append(now)
