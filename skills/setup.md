---
title: Wikipedia MCP Setup & Configuration Guide
description: Step-by-step instructions for human operators and AI agents to configure mcp-server-wikipedia, client harnesses, and token-efficient retrieval workflows.
version: 1.0.0
---

# Wikipedia MCP (`mcp-server-wikipedia`) Setup Guide

Use this playbook to configure `mcp-server-wikipedia` for progressive, token-efficient knowledge retrieval across Wikipedia.

---

## 1. Quick Start (Zero-Auth by Default)

`mcp-server-wikipedia` requires **no API keys, no tokens, and no user accounts**. It connects directly to the official MediaWiki API with progressive disclosure tools to prevent context window bloat.

Test basic connectivity:
- Call `search_wikipedia(query="Artificial Intelligence", limit=3)` to search pages.
- Call `get_page_toc(title="Artificial Intelligence")` to inspect section outlines.

---

## 2. Progressive Retrieval Methodology (Token Optimization)

Rather than dumping entire 50,000-token articles into context:
1. **Discover**: Call `search_wikipedia(query=...)` to identify canonical page titles.
2. **Outline**: Call `get_page_toc(title=...)` to view section headings and index numbers.
3. **Target**: Call `get_page_section(title=..., section_index=...)` to pull only the relevant section.
4. **Synthesize**: Call `get_full_page(title=...)` only when an exhaustive read is strictly required.

---

## 3. Client Harness Configuration

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "wikipedia": {
      "command": "uvx",
      "args": ["mcp-server-wikipedia"]
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "wikipedia": {
      "command": "uvx",
      "args": ["mcp-server-wikipedia"]
    }
  }
}
```

### CLI / NPX
```bash
uvx mcp-server-wikipedia
# or via npx
npx -y mcp-server-wikipedia
```

---

## 4. Troubleshooting & Error Recovery

- **Disambiguation Pages**: If a query returns multiple topics, review the suggested titles in the response and call `get_page_section` with the specific parenthetical topic (e.g. `Mercury (element)` vs `Mercury (planet)`).
- **Missing or Renamed Sections**: If a section index has changed due to a recent edit, re-call `get_page_toc` to fetch the refreshed outline.
