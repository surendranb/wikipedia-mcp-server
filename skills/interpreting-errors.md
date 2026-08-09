# Interpreting errors from wikipedia-mcp-server

Every tool returns a JSON **string**. A failed lookup does NOT raise a protocol
error — the tool call succeeds and the failure is inside the payload. Always
inspect the returned JSON before assuming the data is there.

## The three result shapes

1. **Data** — a list (`search_articles`, `get_summaries`, `get_toc`) or an
   object with a `text` field (`get_section`, `get_page`).
2. **Error object** — `{"error": "<message>"}`. The call "succeeded" but no
   data came back.
3. **Empty success** — valid shape, zero data. `search_articles` returns `[]`
   when nothing matches; `get_page`/`get_section` can return an object whose
   `text` is empty. **An empty success means the page (or section) is missing
   or the query matched nothing — treat it exactly like a not-found error,
   not like a working result.**

## Error messages you will see, and what to do

| Message starts with | Meaning | Recovery |
| --- | --- | --- |
| `query must be a string`, `title must be a string`, `titles must be a list of strings`, `title and section must be strings` | You sent the wrong argument type | Fix the argument type and retry |
| `Failed to get summaries: Unable to fetch summary for '<title>'` (usually a 404) | The exact title does not exist | Call `search_articles` first; use a returned `title` verbatim |
| `Failed to get page: Unable to fetch page '<title>'` | Same — title not found | Same — search first, then use the exact title |
| `Failed to get section: Section '<section>' was not found` | Section name/index doesn't match the page's TOC | Call `get_toc(title)` and pass an exact `index` or `line` value from it |
| `Failed to search articles:` / `Failed to get TOC:` (network/HTTP text follows) | Upstream Wikipedia API problem | Retry once; if it persists, tell the user Wikipedia is unreachable |

## Gotchas

- Titles are case- and punctuation-sensitive. Never guess a title — the
  reliable path is `search_articles` → pick a result → use its `title` field
  unchanged.
- `get_toc` on a nonexistent page does not error: it returns only the synthetic
  `Introduction` entry. A one-entry TOC for a substantial topic is a sign the
  title is wrong.
- `get_section` accepts either the TOC `index` (e.g. `"3"`) or the exact
  section `line` text. Anything else fails.
- Follow the ladder: search → summaries → TOC → section. Fetch `get_page` only
  when you truly need the whole article.
