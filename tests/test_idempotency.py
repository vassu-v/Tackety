"""
Covers the idempotency fix directly against IssueEngine and SupportHub -
this is the correct boundary for it: an HTTP-level retry-after-timeout
test would need to simulate the response arriving after the session was
already closed by the first (successfully processed) attempt, which hits
the closed-session 409 guard before ever reaching the router. That guard
protects a different failure mode (chatting into a dead session) and is
tested separately in test_session_lifecycle.py.

Known interaction, documented rather than silently glossed over: a retry
that arrives after the *server* has already fully processed the original
request and closed the session - but before the *client* received the
response - will get a 409 rather than a deduped replay. Idempotency-Key
still protects the more common case of a retry firing because the
request never reached the server, or the client aborted before the
server's response came back.
"""
import uuid


def test_process_ticket_dedupes_on_client_request_id():
    from engine.issue_engine import IssueEngine
    import tempfile, os
    # Note: sqlite3.connect(':memory:') creates a brand new empty database
    # per connection, which would break dedup logic that depends on
    # reading back a row written by a previous connection - use a real
    # temp file so all connections in this test see the same data.
    path = os.path.join(tempfile.mkdtemp(), "idem_test_issues.db")
    ie = IssueEngine(db_path=path, embedding_dim=8)

    key = str(uuid.uuid4())
    embedding = [0.1] * 8

    first = ie.process_ticket(
        session_id="s1", normalized_data={"normalized_slug": "X", "doc_reference": "Y"},
        raw_summary="same issue", embedding=embedding, client_request_id=key
    )
    second = ie.process_ticket(
        session_id="s1", normalized_data={"normalized_slug": "X", "doc_reference": "Y"},
        raw_summary="same issue", embedding=embedding, client_request_id=key
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["ticket_id"] == second["ticket_id"]
    assert first["cluster_id"] == second["cluster_id"]

    clusters = ie.get_ranked_clusters()
    assert len(clusters) == 1
    assert clusters[0]["weight"] == 1  # not bumped twice


def test_process_ticket_without_key_is_not_deduped():
    """No client_request_id means no idempotency protection - two calls
    are two distinct tickets, as expected."""
    from engine.issue_engine import IssueEngine
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "idem_test_issues2.db")
    ie = IssueEngine(db_path=path, embedding_dim=8, cluster_threshold=0.99)

    embedding = [0.1] * 8
    r1 = ie.process_ticket(session_id="s1", normalized_data={"normalized_slug": "X", "doc_reference": "Y"},
                            raw_summary="issue", embedding=embedding)
    r2 = ie.process_ticket(session_id="s1", normalized_data={"normalized_slug": "X", "doc_reference": "Y"},
                            raw_summary="issue", embedding=embedding)
    assert r1["created"] is True
    assert r2["created"] is True
    assert r1["ticket_id"] != r2["ticket_id"]


def test_enqueue_ticket_dedupes_on_client_request_id():
    from engine.human_queue import SupportHub
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "idem_test_support.db")
    sh = SupportHub(db_path=path)

    key = str(uuid.uuid4())
    first = sh.enqueue_ticket("s1", "refund please", client_request_id=key)
    second = sh.enqueue_ticket("s1", "refund please", client_request_id=key)

    assert first is True
    assert second is False
    cases = sh.get_open_cases()
    assert len(cases["NON_TECHNICAL_TICKETS"]) == 1


def test_enqueue_handover_dedupes_on_client_request_id():
    from engine.human_queue import SupportHub
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "idem_test_support2.db")
    sh = SupportHub(db_path=path)

    key = str(uuid.uuid4())
    first = sh.enqueue_handover("s1", "need a human", client_request_id=key)
    second = sh.enqueue_handover("s1", "need a human", client_request_id=key)

    assert first is True
    assert second is False
    cases = sh.get_open_cases()
    assert len(cases["CHAT_HANDOVERS"]) == 1
