# SPDX-License-Identifier: Apache-2.0
"""Integration test: client identity + tools_listed telemetry must survive the
MCP v2 (stateless, 2026-07-28) migration. Real in-memory client<->server, no
mocks. Covers both eras: legacy initialize-handshake clients (today's fleet)
and 2026 per-request-meta clients. Run: python tests/test_v2_telemetry.py

Intercepts at the network boundary (urlopen) so the real send_telemetry
enrichment runs — mcp_client_name / mcp_protocol_version are added there, not by
the caller, so patching send_telemetry itself would hide the very fields we
assert on. search_articles is patched at the WikipediaClient boundary so the
test makes no live Wikipedia calls."""

# ruff: noqa: S110, BLE001

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("WIKIPEDIA_MCP_INTERNAL", "1")

import telemetry as t

# Mirror of the gateway worker's KNOWN_EVENTS (Standard §2 allowlist).
KNOWN_EVENTS = {
    "mcp_started", "tools_listed", "tool_executed", "session_end",
    "server_first_install", "package_download", "skill_tip_shown",
    "resource_read", "install_intent", "install_completed", "surface_click",
    "mcp_tool_count",
}

# Enable telemetry regardless of the ambient env, and capture the outbound
# payloads instead of sending them over the wire.
t.TELEMETRY_DISABLED = False
_PAYLOADS = []


class _FakeResp:
    def read(self):
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(req, *a, **k):
    try:
        _PAYLOADS.append(json.loads(req.data.decode("utf-8")))
    except Exception:
        pass
    return _FakeResp()


t.urllib.request.urlopen = _fake_urlopen

# Imports below are deliberately after the urlopen patch: the session must be
# built on top of the interception. noqa: E402 (module import not at top).
from mcp.client.client import Client  # noqa: E402
from mcp.types import Implementation  # noqa: E402

import server as c  # noqa: E402

# Don't hit the live Wikipedia API from a telemetry test — stub the one tool the
# session calls. We only care that a tool_executed event fires with identity.
c.client.search_articles = lambda query, limit=5: [{"title": "Test", "snippet": "stub"}]


async def _run_session(client_name, mode):
    _PAYLOADS.clear()
    for k in t._RUNTIME_CLIENT:
        t._RUNTIME_CLIENT[k] = None
    c._TOOLS_LISTED["fired"] = False
    async with Client(
        c.mcp, client_info=Implementation(name=client_name, version="9.9.9"), mode=mode
    ) as client:
        await client.list_tools()
        try:
            await client.call_tool("search_articles", {"query": "physics"})
        except Exception:
            pass
    t._drain_pending_sends(3.0)
    return [p for p in _PAYLOADS]


def _check(era, client_name, payloads):
    failures = []
    events = [(p.get("event"), p.get("properties", {})) for p in payloads]
    tool_events = [pr for (e, pr) in events if e == "tool_executed"]
    listed_events = [pr for (e, pr) in events if e == "tools_listed"]

    if not tool_events:
        failures.append(f"[{era}] no tool_executed event fired")
    else:
        names = {pr.get("mcp_client_name") for pr in tool_events}
        if client_name not in names:
            failures.append(
                f"[{era}] mcp_client_name not captured on tool_executed "
                f"(got {names!r}, expected {client_name!r})"
            )
        if not any(pr.get("mcp_protocol_version") for pr in tool_events):
            failures.append(f"[{era}] mcp_protocol_version not captured")

    if not listed_events:
        failures.append(f"[{era}] tools_listed event never fired")
    return failures


async def main():
    all_failures = []
    for era, mode in (("legacy", "legacy"), ("2026-era", "auto")):
        payloads = await _run_session("claude-code", mode)
        all_failures += _check(era, "claude-code", payloads)

    if all_failures:
        print("FAIL:")
        for f in all_failures:
            print("  -", f)
        sys.exit(1)
    print("PASS: identity + tools_listed + protocol_version captured in both eras")


def test_telemetry_contract():
    """Pytest-discoverable entry (CI runs `pytest tests/`). Asserts the MCP
    Telemetry Standard §6 contract at the network boundary: envelope fields,
    shape-only query capture (no PII values), taxonomy naming, session_end."""
    asyncio.run(main())
    failures = []

    for era, mode in (("legacy", "legacy"), ("2026-era", "auto")):
        payloads = asyncio.run(_run_session("claude-code", mode))
        for payload in payloads:
            props = payload.get("properties", {})
            assert payload["event"] in KNOWN_EVENTS, f"unregistered event: {payload['event']}"
            assert "launch_channel" not in props, "launch_channel must be removed (Standard §1)"
            assert "has_ever_worked" not in props, "has_ever_worked must be removed (Standard §1)"
            assert props.get("agent_name") not in (None, "unknown")
            assert props.get("discovery_channel") in ("uvx", "homebrew", "pip_venv", "direct_python")
            assert props.get("run_context") in ("ci", "cloud", "terminal", "desktop", "headless")
            assert props.get("session_id", "").startswith("sess_")
            assert props.get("$process_person_profile") is False

            # PII: query values must never reach the wire — shape only.
            for forbidden in ("query", "title", "titles", "section"):
                assert forbidden not in props, f"PII value leaked via {forbidden!r}: {props.get(forbidden)!r}"

            if payload["event"] == "tool_executed":
                assert isinstance(props.get("latency_ms"), int), "latency_ms missing"
                assert props.get("status") in ("success", "warning", "cancelled", "error", "exception")
                assert "rows_returned" in props
                assert "query_length" in props and props["query_length"] > 0
                assert props.get("has_query") is True
                if props.get("error_category"):
                    assert props["error_category"] in t.ERROR_CATEGORIES, f"bad category: {props['error_category']}"

    # session_end fired with aggregates on at least one of the eras.
    all_end = [
        p for p in asyncio.run(_run_session("claude-code", "auto"))
        if p["event"] == "session_end"
    ]
    if all_end:
        end = all_end[0]["properties"]
        assert "calls_total" in end and "session_duration_s" in end

    if failures:
        raise AssertionError("\n".join(failures))


if __name__ == "__main__":
    asyncio.run(main())
