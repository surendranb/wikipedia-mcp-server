# Testing Guide

This project supports two testing layers:

- automated unit tests for client logic and response shaping
- manual MCP smoke tests from a fresh Codex chat

## Automated Tests

Run all unit tests:

```bash
cd wikipedia-mcp-server
./.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

These tests cover:

- HTML stripping
- title normalization
- section lookup by index and name
- search result sanitization
- section fetching and plain-text extraction
- page fetching fallback behavior

## Manual MCP Smoke Tests

Open a fresh Codex chat in VS Code and try prompts like these.

### Test 1: Candidate discovery

```text
Use the wikipedia MCP to search for "photosynthesis light dependent reactions" and summarize the top 3 candidate articles.
```

Expected outcome:

- returns multiple pages
- includes `Photosynthesis`
- includes short snippets or summaries rather than a full page dump

### Test 2: Progressive narrowing

```text
Use the wikipedia MCP to answer: "What molecules are produced during the light-dependent reactions of photosynthesis?"
First search, then inspect summaries, then fetch only the most relevant section.
```

Expected outcome:

- model uses multiple MCP calls
- selects `Photosynthesis`
- fetches `Light-dependent reactions`
- answer includes `ATP`, `NADPH`, and `oxygen`

### Test 3: Broad query

```text
Use the wikipedia MCP to answer: "Explain the development and implications of general relativity."
Search broadly first, then decide whether to fetch sections or a full page.
```

Expected outcome:

- model scouts several pages first
- chooses a deeper fetch strategy instead of immediately locking onto one section

### Test 4: Section precision

```text
Use the wikipedia MCP to find the relevant section for "Which elements exhibit superconductivity and what are their critical temperatures?"
Show the candidate article, TOC choice, and the final section fetched.
```

Expected outcome:

- candidate article should be `Superconductivity`
- TOC inspection should happen before the deep fetch
- final fetch should avoid irrelevant sections like generic history if a more targeted one is available

## Retrieval Expectations

Good behavior:

- search first
- compare multiple candidate articles when the query is ambiguous
- prefer summaries and TOC before fetching large bodies of text
- fetch a section when the query is narrow
- fetch a full page only when the answer is broad or distributed

Bad behavior:

- immediate full-page fetch without scouting
- relying on a single top search result without comparing alternatives
- pulling multiple long pages into context when a TOC or section would do
