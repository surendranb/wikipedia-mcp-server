---
layout: layout.njk
title: "Wikipedia MCP Server: Surgical Knowledge Retrieval"
description: "Token-efficient Wikipedia knowledge retrieval MCP server for AI agents with section-level queries and structured JSON returns."
kicker: "KNOWLEDGE RETRIEVAL MCP"
subkicker: "Token-Efficient Encyclopedia"
header_badge: "Section-Level Retrieval · Structured JSON · SQLite Caching · Zero Token Waste"
lede: "Let AI agents query the world's largest encyclopedia without burning context windows. Delivers section-level extracts, summary modes, link graph traversals, and local SQLite caching in structured JSON."
chips:
  - "MCP 2.0"
  - "Section Extraction"
  - "SQLite Cache"
  - "PyPI: mcp-server-wikipedia"
  - "Python Async"
toc:
  - id: "quickstart"
    title: "1. Quickstart"
  - id: "the-challenge"
    title: "2. The Context Waste Challenge"
  - id: "agent-setup"
    title: "3. Agent Configuration"
  - id: "tools-reference"
    title: "4. Tool & Parameter Reference"
  - id: "section-queries"
    title: "5. Surgical Section Queries"
---

<section id="quickstart" class="space-y-6">
<div class="kicker">01 / Getting Started</div>

## Quickstart

Run `wikipedia-mcp` locally with zero configuration:

```bash
# Run with uvx
uvx mcp-server-wikipedia

# Or clone and run directly
git clone https://github.com/surendranb/wikipedia-mcp-server.git
cd wikipedia-mcp-server
pip install -r requirements.txt
python server.py
```

</section>

---

<section id="the-challenge" class="space-y-6">
<div class="kicker">02 / Architecture</div>

## The Context Waste Challenge

LLMs frequently hallucinate historical dates, mathematical definitions, and technical biographies. While Wikipedia contains verified ground truth, dumping raw 15,000-word articles into context windows burns tokens and degrades reasoning.

**Wikipedia MCP provides surgical precision:**

<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
<div class="p-3.5 bg-[#fbfbfa] rounded-lg border border-[#e5e6e4] space-y-1">
<b>1. Section-Level Extraction</b>
<p class="text-[#747982] leading-relaxed !mb-0">Retrieve only the requested section (e.g. `Architecture` of Transformer model) with heading hierarchy.</p>
</div>
<div class="p-3.5 bg-[#fbfbfa] rounded-lg border border-[#e5e6e4] space-y-1">
<b>2. 200-Word Lead Summary</b>
<p class="text-[#747982] leading-relaxed !mb-0">Extract concise article overviews for fast multi-entity verification.</p>
</div>
<div class="p-3.5 bg-[#fbfbfa] rounded-lg border border-[#e5e6e4] space-y-1">
<b>3. Link Graph Traversal</b>
<p class="text-[#747982] leading-relaxed !mb-0">Follow hyperlinked concept graphs recursively without manual prompt chaining.</p>
</div>
<div class="p-3.5 bg-[#fbfbfa] rounded-lg border border-[#e5e6e4] space-y-1">
<b>4. Local SQLite Cache</b>
<p class="text-[#747982] leading-relaxed !mb-0">7-day TTL local cache prevents redundant HTTP round-trips for high-frequency queries.</p>
</div>
</div>

</section>

---

<section id="agent-setup" class="space-y-6">
<div class="kicker">03 / Agent Setup</div>

## Agent Configuration

### Claude Desktop
Add to `claude_desktop_config.json`:

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

### Cursor / Antigravity
Add to IDE settings:

```json
{
  "mcpServers": {
    "wikipedia": {
      "command": "python",
      "args": ["/absolute/path/to/wikipedia-mcp-server/server.py"]
    }
  }
}
```

</section>

---

<section id="tools-reference" class="space-y-6">
<div class="kicker">04 / API & Tools</div>

## Tool & Parameter Reference

| Tool Name | Parameters | Description |
|:---|:---|:---|
| `get_page` | `title`, `sections` | Retrieves full article or specific section text in structured JSON. |
| `get_summary` | `title` | Fast 200-word lead extract. |
| `search_wikipedia` | `query`, `limit` | Full-text search returning page titles and descriptions. |
| `get_links` | `title`, `limit` | Extracts outgoing wiki links from an article. |

</section>

---

<section id="section-queries" class="space-y-6">
<div class="kicker">05 / Example</div>

## Surgical Section Queries

Models can extract exact sections without loading the entire article:

```python
wikipedia.get_page(
    title="Transformer (machine learning model)",
    sections=["Architecture", "Training"]
)
```

</section>
