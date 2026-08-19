"""
Covers the rate limiter on the public /session/start and /session/message
endpoints. The limiter's counters are process-global (see engine/rate_limit.py
docstring for why that's an acceptable scope cut), which would make a naive
test order-dependent - other tests in this suite also call /session/start
and share the same counter. To keep this test deterministic regardless of
run order, it monkeypatches the limit down and clears the shared hit-tracking
dict first, rather than relying on a fresh unused budget.
"""
import engine.rate_limit as rl


def test_exceeding_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(rl, "MAX_REQUESTS_PER_WINDOW", 3)
    rl._hits.clear()

    for _ in range(3):
        res = client.post("/session/start", json={})
        assert res.status_code == 200

    blocked = client.post("/session/start", json={})
    assert blocked.status_code == 429


def test_different_clients_are_not_conflated(client, monkeypatch):
    """The limiter keys on request.client.host - within a single TestClient
    that's constant, so this just documents the assumption rather than
    exercising multi-client behavior (which would need a real network
    client). A regression here would show up as every request in the
    429 test above being blocked from the very first call instead of
    only after the limit is reached."""
    monkeypatch.setattr(rl, "MAX_REQUESTS_PER_WINDOW", 100)
    rl._hits.clear()

    res = client.post("/session/start", json={})
    assert res.status_code == 200
    assert len(rl._hits) == 1
