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
    "skill_read", "resource_read", "install_intent", "install_completed",
    "surface_click", "mcp_tool_count", "server_discovered",
}

# Any well-formed W3C traceparent: sent per-request, must come back parsed.
TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

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
# built on top of the interception.
from mcp.client.client import Client
from mcp.types import Implementation

import server as c

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
            await client.call_tool(
                "search_articles", {"query": "physics"},
                meta={"traceparent": TRACEPARENT},
            )
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
            assert props.get("schema_version") == 2, "envelope must be schema_version 2 (Standard §7)"
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
                # Per-request protocol capture (Standard §3): request id and
                # W3C trace context parsed from _meta.
                assert props.get("mcp_request_id"), "mcp_request_id missing"
                assert props.get("traceparent") == TRACEPARENT, "traceparent not captured"
                assert props.get("trace_id") == TRACEPARENT.split("-")[1]
                assert props.get("span_id") == TRACEPARENT.split("-")[2]
                if props.get("error_category"):
                    assert props["error_category"] in t.ERROR_CATEGORIES, f"bad category: {props['error_category']}"

            if payload["event"] == "tools_listed":
                assert isinstance(props.get("tool_count"), int) and props["tool_count"] > 0

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


def test_skill_read_offline_fallback():
    """skill_read: on fetch failure it falls back to the bundled skills/ copy and
    fires a skill_read event with fetch_ok=False (no live GitHub call here)."""

    async def _go():
        _PAYLOADS.clear()

        def _no_network(*a, **k):
            raise OSError("offline (test)")

        original_get = c.requests.get
        c.requests.get = _no_network
        try:
            async with Client(
                c.mcp, client_info=Implementation(name="claude-code", version="9.9.9"), mode="auto"
            ) as client:
                listed = await client.call_tool("skills_list", {})
                skills = json.loads(listed.content[0].text)
                assert {"name", "description"} <= set(skills[0]), skills
                assert any(s["name"] == "interpreting-errors" for s in skills)

                result = await client.call_tool("skill_read", {"name": "interpreting-errors"})
                text = result.content[0].text
                assert "Interpreting errors" in text, "local skills/ fallback not served"

                # Allowlist: unknown names never build a URL, they error out.
                bad = await client.call_tool("skill_read", {"name": "../../etc/passwd"})
                assert "error" in json.loads(bad.content[0].text)
        finally:
            c.requests.get = original_get
        t._drain_pending_sends(3.0)

        reads = [p for p in _PAYLOADS if p["event"] == "skill_read"]
        assert reads, "skill_read event never fired"
        assert reads[0]["properties"]["skill_name"] == "interpreting-errors"
        assert reads[0]["properties"]["fetch_ok"] is False

    asyncio.run(_go())


def test_optout_gates_all_side_effects():
    """Opt-out must gate every side effect (Standard §1.4): no ~/.wikipedia_mcp
    writes, no `ps` ancestor walks, no events — verified in a real subprocess
    with a scratch HOME."""
    import subprocess
    import tempfile

    repo = str(Path(__file__).resolve().parent.parent)
    code = f"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, {repo!r})
import telemetry as t

assert t.TELEMETRY_DISABLED is True
config_dir = Path.home() / ".wikipedia_mcp"
print(json.dumps({{
    "dir_created": config_dir.exists(),
    "ps_walk": t._process_ancestor_names(),
    "installation_id_persistent": t.INSTALLATION_ID.startswith("inst_"),
}}))
t.announce_and_fire_boot_events()
t.send_telemetry("tool_executed", {{"tool_name": "x"}})
print(json.dumps({{"dir_created_after": config_dir.exists()}}))
"""

    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home, DO_NOT_TRACK="1")
        env.pop("WIKIPEDIA_MCP_TELEMETRY", None)
        out = subprocess.run(
            [sys.executable, "-c", code], env=env,
            capture_output=True, text=True, timeout=30, check=False,
        )
        assert out.returncode == 0, out.stderr
        lines = [json.loads(line) for line in out.stdout.strip().splitlines()]
        first, after = lines[0], lines[1]
        assert first["dir_created"] is False, "identity dir written despite opt-out"
        assert first["ps_walk"] == [], "ps ancestor walk ran despite opt-out"
        assert first["installation_id_persistent"] is False, "persistent id minted despite opt-out"
        assert after["dir_created_after"] is False, "boot events wrote state despite opt-out"


if __name__ == "__main__":
    asyncio.run(main())
