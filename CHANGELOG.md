# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
