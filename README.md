# Wikipedia MCP Server

This project exposes Wikipedia as an MCP server using a progressive retrieval strategy:

1. `search_articles`
2. `get_summaries`
3. `get_toc`
4. `get_section`
5. `get_page`

The design goal is to help an LLM inspect several candidate pages cheaply before choosing what deeper content to fetch.

Why this exists (in simple terms):

- naive Wikipedia integrations often fetch multiple full pages up front, then decide what mattered
- this MCP server supports progressive narrowing so you can shortlist candidates first (search -> summaries -> TOC) and only then fetch deep content (section/page)

## Tools

- `search_articles(query, limit=5)`: top matching pages with snippets
- `get_summaries(titles)`: compact summaries for several candidate pages
- `get_toc(title)`: table of contents / section map for one page
- `get_section(title, section)`: one section by index or title
- `get_page(title)`: full plain-text page

## Install

From PyPI:

```bash
python3 -m pip install wikipedia-mcp-server
```

From source (development):

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
```

To run the benchmark, install the optional benchmark dependency set:

```bash
./.venv/bin/python -m pip install -e ".[benchmark]"
```

## Run

```bash
wikipedia-mcp-server
```

Or directly:

```bash
python server.py
```

## MCP Client Config

Most MCP clients accept a config that looks like this:

```json
{
  "mcpServers": {
    "wikipedia": {
      "command": "wikipedia-mcp-server"
    }
  }
}
```

## Example Prompts

- "Use the wikipedia MCP to search for 'photosynthesis light dependent reactions' and summarize the top 3 candidate pages."
- "Use the wikipedia MCP to answer: What molecules are produced during the light-dependent reactions of photosynthesis? Search first, then fetch only the relevant section."
- "Use the wikipedia MCP to answer: Explain the development and implications of general relativity. Search broadly first, then decide whether to fetch sections or a full page."

## Test

Automated tests:

```bash
./.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

Manual MCP smoke tests:

- see `TESTING.md`

Benchmark:

- see `BENCHMARK.md`

## Suggested Retrieval Ladder

1. Search for several candidate pages.
2. Fetch summaries for the top candidates.
3. Choose one or two pages to inspect more deeply.
4. Fetch a section when the query is narrow.
5. Fetch a full page only when the query is broad or the page is short.

## Notes

- Search and parsing use the MediaWiki Action API.
- Summaries and full-page HTML use the Wikimedia REST API when available.
- Section discovery uses `action=parse&prop=sections` today for compatibility. If Wikimedia shifts the preferred discovery surface further, this can be upgraded to a TOC-oriented path without changing the MCP tool interface.
- The official MCP Python SDK needs a modern Python runtime. This project has been validated locally with Python 3.14 in a project virtualenv.
