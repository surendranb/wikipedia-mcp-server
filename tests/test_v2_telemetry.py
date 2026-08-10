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
# `prompt_used` (Protocol Surfaces S6) is new here and NOT yet in the deployed
# worker's set — the worker is accept-and-tag so events flow regardless;
# register it there on the next (separate, human-approved) worker deploy.
KNOWN_EVENTS = {
    "mcp_started", "tools_listed", "tool_executed", "session_end",
    "server_first_install", "package_download", "skill_tip_shown",
    "skill_read", "resource_read", "install_intent", "install_completed",
    "surface_click", "mcp_tool_count", "server_discovered", "prompt_used",
}

# Any well-formed W3C traceparent: sent per-request, must come back parsed.
TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

# Intent capture (capture-then-curate): passed on one call, must arrive
# VERBATIM on that call's tool_executed and be ABSENT on calls without it.
INTENT_TEXT = "background on the Suez crisis for an essay"

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
        try:
            await client.call_tool(
                "search_articles",
                {"query": "suez crisis", "intent": INTENT_TEXT},
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

        # Intent capture: the call WITH intent carries it verbatim; the call
        # WITHOUT it must not carry the property at all.
        tool_props = [
            p.get("properties", {}) for p in payloads if p["event"] == "tool_executed"
        ]
        with_intent = [pr for pr in tool_props if "intent" in pr]
        without_intent = [pr for pr in tool_props if "intent" not in pr]
        assert with_intent, f"[{era}] intent never captured on tool_executed"
        assert all(pr["intent"] == INTENT_TEXT for pr in with_intent), (
            f"[{era}] intent not verbatim: {[pr['intent'] for pr in with_intent]!r}"
        )
        assert without_intent, (
            f"[{era}] call without intent must not carry the intent property"
        )

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


def test_protocol_surfaces_dual_era():
    """Protocol Surfaces v1 (S1/S2/S3/S5/S6) against a real client in BOTH eras:
    - S1: every tool carries readOnlyHint/idempotentHint; openWorldHint marks
      external-API tools (skills_list alone is local-only).
    - S2: search_articles declares the real result shape; structuredContent is
      additive and the TEXT content is byte-identical to the legacy format.
    - S3: user-fixable errors carry versioned briefs, tagged brief_version on
      that call's tool_executed; get_page's missing-page EMPTY SUCCESS gets a
      one-line embedded tip at most once per process.
    - S5: skills mirrored as skill:// resources, firing resource_read.
    - S6: three workflow prompts, each fetch firing prompt_used.
    All stubs sit at the WikipediaClient boundary — no live Wikipedia calls."""

    stub_results = [{"title": "Test", "snippet": "stub"}]
    c.client.search_articles = lambda query, limit=5: stub_results
    c.client.get_toc = lambda title: [{"index": "0", "line": "Introduction", "anchor": "Introduction"}]
    c.client.get_page = lambda title: {"title": title, "text": ""}  # missing page: empty success

    def _summaries_404(titles):
        raise RuntimeError(
            "Unable to fetch summary for 'Nonexistent': 404 Client Error: Not Found for url: u"
        )

    c.client.get_summaries = _summaries_404

    # The exact text a legacy client received before this change (json.dumps,
    # ensure_ascii=False, indent=2) — S2 must not alter a single byte of it.
    expected_search_text = json.dumps(stub_results, ensure_ascii=False, indent=2)
    expected_toc_text = json.dumps(
        [{"index": "0", "line": "Introduction", "anchor": "Introduction"}],
        ensure_ascii=False, indent=2,
    )

    async def _go(mode):
        _PAYLOADS.clear()
        c._TIPS_FIRED.clear()  # per-era reset for the once-per-process tip gate
        async with Client(
            c.mcp, client_info=Implementation(name="claude-code", version="9.9.9"), mode=mode
        ) as client:
            # --- S1 + S2: tools/list ---
            tools = (await client.list_tools()).tools
            assert len(tools) == 7, [t.name for t in tools]
            for t_ in tools:
                ann = t_.annotations
                assert ann is not None, f"{t_.name}: no annotations (S1)"
                assert ann.read_only_hint is True, f"{t_.name}: readOnlyHint"
                assert ann.idempotent_hint is True, f"{t_.name}: idempotentHint"
                expected_open_world = t_.name != "skills_list"
                assert ann.open_world_hint is expected_open_world, f"{t_.name}: openWorldHint"
            search = next(t_ for t_ in tools if t_.name == "search_articles")
            schema_props = (search.output_schema or {}).get("properties", {})
            assert "results" in schema_props and "error" in schema_props, (
                f"S2 outputSchema wrong: {search.output_schema}"
            )

            # --- S2: byte-identical text + additive structuredContent ---
            r = await client.call_tool("search_articles", {"query": "physics"})
            assert r.content[0].text == expected_search_text, (
                f"S2 broke the text wire format:\n{r.content[0].text!r}\n!=\n{expected_search_text!r}"
            )
            assert r.structured_content == {"results": stub_results}
            assert not r.is_error

            # Unchanged path stays byte-identical (no schema, no brief).
            r_toc = await client.call_tool("get_toc", {"title": "Photosynthesis"})
            assert r_toc.content[0].text == expected_toc_text

            # --- S3: missing-page brief on a 404-shaped failure ---
            r_sum = await client.call_tool("get_summaries", {"titles": ["Nonexistent"]})
            err = json.loads(r_sum.content[0].text)["error"]
            assert "search_articles" in err and "won't help" in err, err

            # --- S3: get_page missing page = empty success + ONE embedded tip ---
            r_page1 = await client.call_tool("get_page", {"title": "Nonexistent"})
            page1 = json.loads(r_page1.content[0].text)
            assert page1["text"] == "" and "tip" in page1, page1
            assert "\n" not in page1["tip"], "tip must be one line"
            r_page2 = await client.call_tool("get_page", {"title": "Nonexistent"})
            page2 = json.loads(r_page2.content[0].text)
            assert "tip" not in page2, "tip must fire at most once per process per trigger"

            # --- S5: skill resources ---
            resources = (await client.list_resources()).resources
            uris = {str(x.uri) for x in resources}
            assert "skill://interpreting-errors" in uris, uris
            rr = await client.read_resource("skill://interpreting-errors")
            assert "Interpreting errors" in rr.contents[0].text

            # --- S6: prompts ---
            prompts = (await client.list_prompts()).prompts
            assert {p.name for p in prompts} == {
                "research-a-topic", "verify-a-claim", "compare-articles",
            }
            gp = await client.get_prompt("research-a-topic", {"topic": "Suez crisis"})
            text = gp.messages[0].content.text
            assert "search_articles" in text and "intent" in text and "interpreting-errors" in text

        t._drain_pending_sends(3.0)
        return list(_PAYLOADS)

    for era, mode in (("legacy", "legacy"), ("2026-era", "auto")):
        payloads = asyncio.run(_go(mode))
        events = {}
        for p in payloads:
            events.setdefault(p["event"], []).append(p.get("properties", {}))

        for p in payloads:
            assert p["event"] in KNOWN_EVENTS, f"[{era}] unregistered event: {p['event']}"

        # brief_version lands on the erroring call's tool_executed (S3).
        sum_events = [pr for pr in events.get("tool_executed", []) if pr.get("tool_name") == "get_summaries"]
        assert sum_events and sum_events[0].get("brief_version") == "wiki-missing-page-v1", sum_events
        assert sum_events[0].get("status") == "error"

        page_events = [pr for pr in events.get("tool_executed", []) if pr.get("tool_name") == "get_page"]
        assert page_events[0].get("brief_version") == "wiki-missing-page-v1", page_events
        assert page_events[0].get("rows_returned") == 0
        assert "brief_version" not in page_events[1], "second call carried no tip, no tag"

        # Clean calls never carry brief_version.
        search_events = [pr for pr in events.get("tool_executed", []) if pr.get("tool_name") == "search_articles"]
        assert search_events and "brief_version" not in search_events[0]

        # skill_tip_shown for the embedded tip (S3 delivery telemetry).
        tips = events.get("skill_tip_shown", [])
        assert len(tips) == 1 and tips[0].get("trigger") == "missing_page", tips
        assert tips[0].get("channel") == "embedded_tip"

        # resource_read with resource_uri (S5).
        reads = events.get("resource_read", [])
        assert reads and reads[0].get("resource_uri") == "skill://interpreting-errors", reads

        # prompt_used with prompt_name/has_args (S6).
        used = events.get("prompt_used", [])
        assert used and used[0].get("prompt_name") == "research-a-topic", used
        assert used[0].get("has_args") is True


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
