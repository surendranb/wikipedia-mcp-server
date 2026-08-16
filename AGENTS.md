# AGENTS.md — Agent Operational Manual

> **Canonical context and operating procedures for AI agents (Claude Code, Cursor, Codex, Gemini, Antigravity, OpenCode, Aider) operating on or integrating `wikipedia-mcp-server`.**

---

## 1. System Identity & Mission

- **Repository**: `surendranb/wikipedia-mcp-server`
- **Package Name**: `mcp-server-wikipedia` (PyPI) / `mcp-server-wikipedia` (NPM)
- **Live Portal**: [https://wikipedia.builditwithai.xyz](https://wikipedia.builditwithai.xyz)
- **Purpose**: Surgical, token-efficient Wikipedia knowledge retrieval MCP server for AI agents with summary, search, and full-article markdown.

---

## 2. Quickstart & Invocation for Agents

Agents integrating or executing this server should use stdio transport via either runtime:

```bash
# Python runtime (FastMCP / stdio)
uvx mcp-server-wikipedia

# Universal 1-line auto-installer
curl -fsSL "https://wikipedia.builditwithai.xyz/install" | bash
```

### Environment Variables
- None required (Zero configuration needed).


---

## 3. Tool Reference & Capabilities

| Tool | Capability Summary |
|---|---|
| `get_summary` | Fetches concise factual lead summary. |
| `get_article` | Fetches complete article formatted in clean Markdown. |
| `search` | Searches articles with autocomplete and ranking. |
| `get_section` | Retrieves specific section by title. |
| `get_links` | Extracts outgoing cross-references. |
| `get_categories` | Lists article taxonomic categories. |
| `skill_read` | Loads research playbooks dynamically from GitHub. |
| `skills_list` | Lists all available Wikipedia research skills. |

---

## 4. Agent Working Laws (Operational Rules)

When contributing code, diagnosing bugs, or modifying this repository, all visiting agents must adhere strictly to these rules:

1. **Truth Over Guessing**: Never fabricate responses, schema types, or error reasons. Run native verification scripts before asserting completion.
2. **Shortest Working Diff (Lazy Senior Dev)**: Do not introduce unrequested abstractions, extra dependencies, or architectural bloat. Standard library and native platform features first.
3. **Preserve Schema Stability**: Never remove or rename existing MCP tool parameters without strict backwards-compatibility layers.
4. **Strict Telemetry Boundaries**: Diagnostic telemetry is non-PII and strictly opt-out. Never log user queries, credentials, file contents, or environment variables. Honor `DO_NOT_TRACK=1` and `MCP_TELEMETRY_OPT_OUT=1`.
5. **No Direct Main Commits**: Always create a feature or fix branch before modifying code.

---

## 5. Verification & Test Protocol

Before marking any task as complete in this repository, run the test suite:

```bash
# Run automated verification suite
uv run pytest -v || python3 -m unittest
```

---

## 6. Plugin & Marketplace Discovery Pointers

- **Claude Code**: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
- **Gemini CLI / Antigravity**: `gemini-extension.json`
- **Smithery.ai**: `smithery.yaml`
- **Official MCP Registry & Glama**: `server.json`
- **OpenAI / ChatGPT Actions**: `.well-known/ai-plugin.json`
- **AI Search Crawlers (GEO)**: `llms.txt`
