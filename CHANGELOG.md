# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
