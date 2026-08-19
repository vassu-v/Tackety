"""
Developer/agent-facing API key authentication.

Tackety's customer-facing endpoints (/session/*) stay open - that's the
public chat surface. But everything a developer or support agent uses to
read or mutate ticket data (the queue, cluster resolution, webhook
registration) was previously wide open to anyone who found the URL. That's
a real data-exposure and SSRF risk, not a hypothetical one - see DESIGN.md
and the phase-0 hardening notes for the reasoning.

Usage: set TACKETY_API_KEY in engine/.env. If it's not set, we generate a
random key on startup and print it once so local/dev runs still work
without extra setup - but that key does not persist across restarts, so
anyone deploying for real should set TACKETY_API_KEY explicitly.
"""
import os
import secrets

_env_key = os.getenv("TACKETY_API_KEY")
if _env_key:
    API_KEY = _env_key
    _GENERATED = False
else:
    API_KEY = secrets.token_urlsafe(24)
    _GENERATED = True


def announce_key():
    """Prints the active API key at startup if it was auto-generated."""
    if _GENERATED:
        print("\n" + "=" * 64)
        print("  No TACKETY_API_KEY set in engine/.env - generated one for")
        print("  this run only. It will change on every restart.")
        print(f"\n  X-API-Key: {API_KEY}\n")
        print("  Set TACKETY_API_KEY in engine/.env to keep it stable.")
        print("=" * 64 + "\n")


def verify_api_key(provided: str) -> bool:
    """Constant-time comparison to avoid timing side-channels."""
    if not provided:
        return False
    return secrets.compare_digest(provided, API_KEY)
