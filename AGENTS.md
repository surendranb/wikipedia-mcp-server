# AGENTS.md — Codebase Operational Guide for AI Agents

> **Context, architecture, file map, and execution commands for AI coding agents (Claude Code, Cursor, Codex, Gemini, Antigravity, OpenCode, Aider) working on `wikipedia-mcp-server`.**

---

## 1. Codebase Overview

- **Language & Runtime**: Python 3.10+ (`mcp` FastMCP, `httpx`, `beautifulsoup4`, `pydantic`).
- **Package Name**: `mcp-server-wikipedia` (PyPI) / `mcp-server-wikipedia` (NPM thin wrapper).
- **Core Function**: Surgical, token-efficient Wikipedia knowledge retrieval for AI agents: lead summaries, full article bodies in clean Markdown, live search, section extraction, and taxonomy navigation.

---

## 2. Directory & File Map

```
wikipedia-mcp-server/
├── src/wikipedia_mcp/
│   ├── __init__.py            # Package export
│   ├── server.py              # FastMCP server, tool implementations (get_summary, get_article, search, etc.)
│   ├── client.py              # Wikipedia REST API v1 client with HTTP caching and user-agent headers
│   └── telemetry.py           # Edge Schema v2 telemetry client
├── npm/                       # Thin Node.js CLI launcher
│   ├── bin/index.js           # Subprocess wrapper spawning uvx mcp-server-wikipedia
│   └── package.json           # NPM package metadata
├── tests/                     # Unit and integration test suite
│   ├── test_server.py         # FastMCP tool interface tests
│   ├── test_client.py         # HTTP client & Wikipedia API parsing tests
│   └── test_telemetry.py      # Telemetry & DNT opt-out tests
├── pyproject.toml             # Python packaging metadata (mcp-server-wikipedia)
├── smithery.yaml              # Smithery.ai marketplace configuration
├── server.json                # Official MCP registry specification
├── gemini-extension.json      # Google Gemini / Antigravity extension manifest
├── .claude-plugin/            # Claude Code plugin manifests (plugin.json, marketplace.json)
└── .well-known/ai-plugin.json # OpenAI / ChatGPT Actions manifest
```

---

## 3. Development & Testing Commands

```bash
# Install dependencies in editable mode
uv sync || pip install -e ".[dev]"

# Run the MCP server locally in stdio mode
uv run python -m wikipedia_mcp.server

# Run the test suite
uv run pytest tests/ -v

# Run linting checks
uv run ruff check .
```

---

## 4. Tool Implementation Invariants & Gotchas

1. **Wikipedia API Guidelines (`client.py`)**:
   - Requests to Wikimedia APIs MUST send a descriptive `User-Agent` header (e.g. `WikipediaMCP/0.5.1 (https://github.com/surendranb/wikipedia-mcp-server; contact@builditwithai.xyz)`). Anonymous requests without a User-Agent are blocked with HTTP 403.
2. **HTML to Clean Markdown Transformation**:
   - `get_article` and `get_section` strip navigation boxes, citation tags (`[1]`), edit links, and infobox bloat to minimize token usage for the LLM.
3. **Disambiguation Handling**:
   - When a query hits a disambiguation page, return a clear list of disambiguation options with exact page titles.
