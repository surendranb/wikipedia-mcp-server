# Wikipedia MCP Server 📚

> **Surgical, token-efficient Wikipedia knowledge retrieval MCP server for AI agents with deterministic summary, search, and full-article projection.**

[![CI](https://github.com/surendranb/wikipedia-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/surendranb/wikipedia-mcp-server/actions)
[![PyPI version](https://img.shields.io/pypi/v/mcp-server-wikipedia.svg?style=flat-square&color=blue)](https://pypi.org/project/mcp-server-wikipedia/)
[![npm version](https://img.shields.io/npm/v/mcp-server-wikipedia.svg?style=flat-square&color=red)](https://www.npmjs.com/package/mcp-server-wikipedia)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/surendranb/wikipedia-mcp-server/badge)](https://scorecard.dev/viewer/?site=github.com/surendranb/wikipedia-mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

🌐 **Live Documentation & Web Portal**: [https://wikipedia.builditwithai.xyz](https://wikipedia.builditwithai.xyz)

---

## ⚡ Quickstart

```bash
# 1-Line Universal Installer (Auto-configures Claude Desktop, Cursor, Claude Code, Antigravity, VS Code, Zed, Windsurf)
curl -fsSL "https://wikipedia.builditwithai.xyz/install" | bash

# Or run directly via your preferred runtime:
uvx mcp-server-wikipedia
npx -y mcp-server-wikipedia
```

---

---

## 🤖 Client Setup

### A. Claude Code (CLI)
```bash
claude mcp add wikipedia -- uvx mcp-server-wikipedia
```

### B. Cursor & Google Antigravity (`mcp.json`)
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

### C. Claude Desktop (`claude_desktop_config.json`)
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

### D. VS Code (Cline / Roo Code / Continue)
```json
{
  "mcpServers": {
    "wikipedia": {
      "command": "npx",
      "args": ["-y", "mcp-server-wikipedia"]
    }
  }
}
```

---

## 🛠️ Tools & Capabilities

| Tool Name | Parameters | Description | Return Type |
|---|---|---|---|
| `get_summary` | `title` (string), `lang` (optional) | Fetches concise, factual lead summary of any Wikipedia page. | `string` |
| `get_article` | `title` (string), `lang` (optional) | Fetches complete article body formatted in clean, structured Markdown. | `string` |
| `search` | `query` (string), `limit` (int), `lang` (optional) | Searches Wikipedia articles with autocomplete and relevance ranking. | `JSON` |
| `get_section` | `title` (string), `section_title` (string), `lang` (optional) | Retrieves a specific section by header name, saving context window space. | `string` |
| `get_links` | `title` (string), `lang` (optional) | Extracts outgoing cross-reference links from an article. | `JSON` |
| `get_categories` | `title` (string), `lang` (optional) | Lists taxonomic categories and classifications for a page. | `JSON` |
| `skill_read` | `skill_name` (string) | Dynamically loads research playbooks from GitHub. | `Markdown` |
| `skills_list` | *(none)* | Lists all available Wikipedia research skills. | `JSON` |

---

## 🔒 Telemetry & Privacy

This package collects anonymous, non-PII diagnostic telemetry (command executions, latency, error codes) to improve tool reliability. No article search terms, personal data, source code, or environment variables are ever collected or stored.

You can opt out anytime by setting either of the following environment variables:
```bash
export DO_NOT_TRACK=1
# or
export MCP_TELEMETRY_OPT_OUT=1
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
