from __future__ import annotations

# ruff: noqa: S110, BLE001
import asyncio
import atexit
import contextvars
import functools
import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

import requests
from mcp.server.mcpserver import MCPServer

import telemetry


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in {"p", "section", "div", "li", "ul", "ol", "br", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in {"p", "section", "div", "li", "ul", "ol", "br", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        raw = unescape(" ".join(self._parts))
        compact = re.sub(r"[ \t]+", " ", raw)
        compact = re.sub(r" *\n *", "\n", compact)
        return re.sub(r"\n\s*\n+", "\n\n", compact).strip()


def strip_html(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.text()


def title_key(title: str) -> str:
    return quote(title.replace(" ", "_"), safe="():'%")


@dataclass
class WikipediaClient:
    timeout_seconds: float = 20.0
    user_agent: str = "wikipedia-mcp-server/0.1"

    REST_BASES = (
        "https://en.wikipedia.org/api/rest_v1",
        "https://en.wikipedia.org/w/rest.php/v1",
    )
    ACTION_API = "https://en.wikipedia.org/w/api.php"

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def _get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.text

    def search_articles(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        payload = self._get_json(
            self.ACTION_API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "utf8": 1,
                "srlimit": max(1, min(limit, 10)),
                "srprop": "snippet",
            },
        )
        results: list[dict[str, str]] = []
        for item in payload.get("query", {}).get("search", []):
            results.append(
                {
                    "title": item["title"],
                    "snippet": re.sub(r"<.*?>", "", item.get("snippet", "")).strip(),
                }
            )
        return results

    def get_summary(self, title: str) -> dict[str, Any]:
        key = title_key(title)
        last_error: Exception | None = None
        for base in self.REST_BASES:
            for url in (f"{base}/page/summary/{key}", f"{base}/page/{key}/summary"):
                try:
                    payload = self._get_json(url)
                    return {
                        "title": payload.get("title", title),
                        "description": payload.get("description", ""),
                        "extract": payload.get("extract", ""),
                        "content_urls": payload.get("content_urls", {}),
                    }
                except Exception as exc:
                    last_error = exc
        raise RuntimeError(f"Unable to fetch summary for {title!r}: {last_error}")

    def get_summaries(self, titles: Sequence[str]) -> list[dict[str, Any]]:
        return [self.get_summary(title) for title in titles]

    def get_toc(self, title: str) -> list[dict[str, str]]:
        payload = self._get_json(
            self.ACTION_API,
            params={
                "action": "parse",
                "page": title,
                "prop": "sections",
                "format": "json",
            },
        )
        raw_sections = payload.get("parse", {}).get("sections", [])
        sections = [{"index": "0", "line": "Introduction", "anchor": "Introduction"}]
        for section in raw_sections:
            sections.append(
                {
                    "index": str(section.get("index", "")),
                    "line": str(section.get("line", "")).strip(),
                    "anchor": str(section.get("anchor", "")).strip(),
                }
            )
        return sections

    def get_section(self, title: str, section: str) -> dict[str, Any]:
        toc = self.get_toc(title)
        section_index = self._resolve_section_index(toc, section)
        params: dict[str, Any] = {
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
            "disableeditsection": 1,
            "disabletoc": 1,
        }
        if section_index != "0":
            params["section"] = section_index
        payload = self._get_json(self.ACTION_API, params=params)
        html = payload.get("parse", {}).get("text", {}).get("*", "")
        return {
            "title": title,
            "section": self._resolve_section_line(toc, section_index),
            "section_index": section_index,
            "text": strip_html(html),
        }

    def get_page(self, title: str) -> dict[str, Any]:
        key = title_key(title)
        last_error: Exception | None = None
        for base in self.REST_BASES:
            for url in (f"{base}/page/html/{key}", f"{base}/page/{key}/html"):
                try:
                    html = self._get_text(url)
                    return {"title": title, "text": strip_html(html)}
                except Exception as exc:
                    last_error = exc

        try:
            payload = self._get_json(
                self.ACTION_API,
                params={"action": "parse", "page": title, "prop": "text", "format": "json"},
            )
            html = payload.get("parse", {}).get("text", {}).get("*", "")
            return {"title": title, "text": strip_html(html)}
        except Exception as exc:
            last_error = exc

        raise RuntimeError(f"Unable to fetch page {title!r}: {last_error}")

    @staticmethod
    def _resolve_section_index(toc: Sequence[dict[str, str]], section: str) -> str:
        normalized = section.strip().lower()
        for item in toc:
            if item["index"] == section:
                return item["index"]
            if item["line"].strip().lower() == normalized:
                return item["index"]
        raise ValueError(f"Section {section!r} was not found")

    @staticmethod
    def _resolve_section_line(toc: Sequence[dict[str, str]], index: str) -> str:
        for item in toc:
            if item["index"] == index:
                return item["line"]
        return index


client = WikipediaClient()
mcp = MCPServer("wikipedia-mcp-server", version=telemetry.MCP_SERVER_VERSION)

# The request currently being served, exposed to telemetry that needs per-request
# context. MCP 2.0 is stateless — there is no persistent request_context on the
# server — so the middleware stashes each request here.
_CURRENT_REQUEST = contextvars.ContextVar("wikipedia_current_request", default=None)
_TOOLS_LISTED = {"fired": False}


async def _telemetry_middleware(ctx, call_next):
    """Runs for EVERY request (initialize, server/discover, tools/list, tools/call,
    ...). In MCP 2.0 the v1 `mcp._mcp_server.request_context` read is gone;
    middleware is the supported, era-agnostic hook that receives the
    ServerRequestContext directly. Responsibilities:
      1. expose the request to per-request telemetry via _CURRENT_REQUEST
      2. capture client identity (dual-era: handshake session OR per-request _meta)
      3. fire tools_listed once — the 'connected but never called a tool' signal
    """
    _CURRENT_REQUEST.set(ctx)
    try:
        telemetry.capture_client_info(ctx)
    except Exception:
        pass
    try:
        if getattr(ctx, "method", None) == "tools/list" and not _TOOLS_LISTED["fired"]:
            _TOOLS_LISTED["fired"] = True
            telemetry.send_telemetry("tools_listed", {
                "seconds_since_boot": round(time.time() - _BOOT_TS, 1),
            })
    except Exception:
        pass
    return await call_next(ctx)


mcp.middleware.append(_telemetry_middleware)


def _count_rows(result: Any) -> int:
    """Count the ITEMS OF DATA a tool returned — the definitive 'it worked'
    signal (0 = no data). Shape-aware, since the count only means something if
    it maps to the tool's unit of data:
      - list results  -> len   (search=# articles, summaries=# summaries, toc=# sections)
      - one content object (get_page/get_section: a dict with 'text') -> 1 if it
        carries real text, else 0 — NOT its field count
      - error/missing-shaped payload -> 0
    Tools return json.dumps(...) strings."""
    if result is None:
        return 0
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except Exception:
        s = result.strip() if isinstance(result, str) else ""
        return 1 if s and s not in ("[]", "{}", "null") else 0
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        if parsed.get("error") or parsed.get("missing"):
            return 0
        if "text" in parsed:  # a single page/section object
            return 1 if str(parsed.get("text") or "").strip() else 0
        return 1 if parsed else 0
    return 1 if parsed else 0


def with_telemetry(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        error = None        # exception class name, or "ToolError" for JSON error returns
        error_message = None
        result = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = type(e).__name__
            error_message = str(e)
            raise
        finally:
            duration = time.time() - start_time
            rows = _count_rows(result)
            
            is_json_error = False
            if not error and isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict) and "error" in parsed:
                        is_json_error = True
                        error = "ToolError"
                        error_message = parsed["error"]
                except Exception:
                    pass

            props = {
                "tool_name": func.__name__,
                "latency_ms": int(duration * 1000),
                "status": "error" if (error or is_json_error) else "success",
                "rows_returned": rows,
                "result_chars": len(result) if isinstance(result, str) else 0,
            }
            if error:
                props["error_category"] = (
                    error if error in telemetry.ERROR_CATEGORIES else "InternalError"
                )
                if error_message:
                    props["error_message"] = telemetry.scrub(error_message)

            # Query shape only — never the query/title VALUES themselves (PII).
            if "query" in kwargs:
                props["has_query"] = True
                props["query_length"] = len(kwargs["query"])
            if "title" in kwargs:
                props["has_query"] = True
                props["query_length"] = len(kwargs["title"])
            if "titles" in kwargs:
                props["n_titles"] = len(kwargs["titles"])
            if "section" in kwargs:
                props["has_section"] = bool(kwargs["section"])

            _record_call(func.__name__, props)

            telemetry.send_telemetry("tool_executed", props)
    return wrapper


def _record_call(tool_name: str, props: dict[str, Any]) -> None:
    """Session-level capture: ordered tool sequence (names only), per-tool
    counts, and latency from process boot to first call (handshake proxy)."""
    _TOOL_SEQUENCE.append(tool_name)
    if len(_TOOL_SEQUENCE) > 100:
        _TOOL_SEQUENCE.pop(0)
    _TOOL_COUNTS[tool_name] = _TOOL_COUNTS.get(tool_name, 0) + 1
    if _FIRST_CALL[0]:
        props["first_tool_latency_ms"] = int((time.time() - _BOOT_TS) * 1000)
        _FIRST_CALL[0] = False


_BOOT_TS = time.time()
_TOOL_SEQUENCE: list[str] = []
_TOOL_COUNTS: dict[str, int] = {}
_FIRST_CALL = [True]


def _send_session_end() -> None:
    if not _TOOL_SEQUENCE:
        return
    telemetry.send_telemetry("session_end", {
        "tool_sequence": list(_TOOL_SEQUENCE),
        "tool_counts": dict(_TOOL_COUNTS),
        "calls_total": len(_TOOL_SEQUENCE),
        "session_duration_s": int(time.time() - _BOOT_TS),
    })


atexit.register(_send_session_end)


@mcp.tool()
@with_telemetry
def search_articles(query: str, limit: int = 5) -> str:
    """Search English Wikipedia and return a compact list of candidate pages."""
    if not isinstance(query, str):
        return json.dumps({"error": "query must be a string"}, ensure_ascii=False, indent=2)
    try:
        return json.dumps(client.search_articles(query, limit=limit), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to search articles: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
@with_telemetry
def get_summaries(titles: list[str]) -> str:
    """Fetch compact summaries for one or more Wikipedia page titles."""
    if not isinstance(titles, list):
        return json.dumps({"error": "titles must be a list of strings"}, ensure_ascii=False, indent=2)
    try:
        return json.dumps(client.get_summaries(titles), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to get summaries: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
@with_telemetry
def get_toc(title: str) -> str:
    """Return a page's table of contents as section index, title, and anchor."""
    if not isinstance(title, str):
        return json.dumps({"error": "title must be a string"}, ensure_ascii=False, indent=2)
    try:
        return json.dumps(client.get_toc(title), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to get TOC: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
@with_telemetry
def get_section(title: str, section: str) -> str:
    """Fetch one section by section index or exact section title."""
    if not isinstance(title, str) or not isinstance(section, str):
        return json.dumps({"error": "title and section must be strings"}, ensure_ascii=False, indent=2)
    try:
        return json.dumps(client.get_section(title, section), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to get section: {e}"}, ensure_ascii=False, indent=2)


@mcp.tool()
@with_telemetry
def get_page(title: str) -> str:
    """Fetch a full Wikipedia page as plain text."""
    if not isinstance(title, str):
        return json.dumps({"error": "title must be a string"}, ensure_ascii=False, indent=2)
    try:
        return json.dumps(client.get_page(title), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to get page: {e}"}, ensure_ascii=False, indent=2)


def main() -> None:
    telemetry.announce_and_fire_boot_events()
    telemetry.send_telemetry("mcp_started")

    async def _run() -> None:
        # tools_listed now fires from the telemetry middleware on the client's
        # real tools/list request (the 'connected but never called' sensor), so
        # boot no longer self-enumerates a duplicate. mcp_tool_count is a stable
        # boot-time count, kept for the feature-set/regression check.
        tools = await mcp.list_tools()
        telemetry.send_telemetry("mcp_tool_count", {"tool_count": len(tools)})
        await mcp.run_stdio_async()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
