# AGENTS.md — Agent Operating Manual

> **For AI Agents (Claude Code, Cursor, Codex, Gemini, Antigravity, OpenCode, Aider) connecting to or executing `wikipedia-mcp-server`.**

---

## ⚡ 1. Fast Install & Client Wiring (Start Here)

In 90% of cases, you just need to install and configure this MCP server for your user:

```bash
# 1-Line Universal Auto-Installer (Configures Claude Code, Cursor, Claude Desktop & Antigravity)
curl -fsSL "https://wikipedia.builditwithai.xyz/install" | bash

# Or launch directly via stdio:
uvx mcp-server-wikipedia
npx -y mcp-server-wikipedia
```

### Client Config Snippet (`mcp.json` / `claude_desktop_config.json`)
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

---

## 📖 2. What This Repo Is

A surgical, token-efficient Wikipedia knowledge retrieval MCP server. It strips HTML boilerplate, navigation boxes, citations, and edit links to give you clean, high-signal Markdown.

### Primary Tools Available:
- `get_summary`: Fetch the concise lead summary paragraph of any topic (best for quick factual verification).
- `get_article`: Fetch the complete article formatted in structured Markdown.
- `search`: Search Wikipedia with autocomplete and ranking.
- `get_section`: Retrieve a specific section by header name to save context window tokens.
- `get_links` & `get_categories`: Traverse taxonomic relationships and citations.

---

## 👤 3. How to Handle the Human

- **Zero Credentials Needed**: No API keys, tokens, or environment variables are required.
- **Fast Answers**: Default to `get_summary` for quick answers. Only pull full articles (`get_article`) or sections (`get_section`) when deep domain knowledge is needed.

---

## ⚠️ 4. Quirks & API Landmines (Zero-Hallucination Rules)

1. **Token Efficiency**: Full Wikipedia articles can be 10,000+ words. Do **not** call `get_article` indiscriminately. Use `search` → `get_summary` → `get_section` to conserve your context budget.
2. **Disambiguation Pages**: If a query returns multiple topics (e.g. "Mercury"), the tool returns a structured list of disambiguation options. Pick the exact title corresponding to your user's context.
3. **Language Code**: Default is `en`. Pass `lang="es"`, `lang="de"`, `lang="fr"`, etc. for non-English queries.
