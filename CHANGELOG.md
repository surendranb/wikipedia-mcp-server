# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2026-08-09

### Changed
- Telemetry: stop capturing query/title/titles/section VALUES (PII) — shape only (`has_query`, `query_length`, `n_titles`, `has_section`).
- Telemetry: align naming to the MCP Telemetry Standard — `latency_ms` (was `duration_ms`), `error_category`/`error_message` (scrubbed, was `error`); remove `launch_channel` + `has_ever_worked` from the envelope; drop verbatim `client_instructions` (keep shape flags).
- Telemetry: `session_end` now carries `session_duration_s`.
- Gateway worker: add standard guards — malformed event-name rejection (400), allowlist rejection (400), default-library UA rejection (403) with `x-wikipedia-mcp-internal` bypass, `traffic_class` internal|external. Redeployed with current KNOWN_EVENTS (687 `mcp_tool_count` + `session_end` events were flagged `unregistered_event` on the stale deployment).
- Tests: contract test now pytest-discoverable (was script-only, never ran in CI); asserts envelope, PII-free wire, taxonomy naming, session aggregates.

## [0.2.3] - 2026-08-04

### Fixed
- Telemetry: Update exception handler to explicitly set `properties.status = 'error'` when exceptions are caught (SUR-240).
- Tools: Add defensive parameter validation and graceful JSON error payloads for `search_articles`, `get_summaries`, `get_toc`, `get_section`, and `get_page` to prevent bot crashes from unhandled HTTPError, RuntimeError, or TypeError exceptions (SUR-240).

## [0.1.8] - 2026-07-31

### Added
- Telemetry: capture client `instructions` from the initialize handshake (presence flag, length, truncated content).
- Telemetry: `session_end` event with ordered tool sequence and per-tool counts for usage-pattern analysis.
- Telemetry: `first_tool_latency_ms` (process boot to first tool call) as a handshake-timing proxy.

### Fixed
- Compatibility with MCP SDK 1.29 FastMCP API (`list_tools`, `run_stdio_async`); the server crashed on start with newer SDK versions.

## [0.1.0] - 2026-04-17

### Added
- Initial release of the Wikipedia MCP Server.
- Tool: `search_articles` for candidate discovery.
- Tool: `get_summaries` for compact page evaluation.
- Tool: `get_toc` for section discovery.
- Tool: `get_section` for surgical text retrieval.
- Tool: `get_page` for full-page fallback.
- Support for MediaWiki Action API and Wikimedia REST API.
- Token efficiency benchmark suite (scripts/benchmark_token_efficiency.py).
- Basic unit tests for HTML stripping and section resolution.
