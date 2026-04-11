# Benchmark

This benchmark is designed to test the actual thesis of this MCP server:

An LLM often needs to inspect multiple candidate Wikipedia pages before it knows which pages deserve deeper reading. A naive integration fetches full pages too early. This MCP server should let the model scout candidates cheaply first, then spend large context only on the pages or sections that survive that filtering step.

## Claim Being Tested

We are not trying to prove that this server magically makes every Wikipedia question cheap.

We are trying to prove a narrower and more defensible claim:

- when a model would otherwise fetch the top few candidate pages in full
- and only later realize that only one or two of those pages or sections were actually needed
- the MCP retrieval ladder reduces token usage by delaying deep fetches until after candidate selection

## Benchmark Design

Each benchmark case uses the same user query for two retrieval strategies.

### Strategy A: Naive direct Wikipedia retrieval

This simulates a straightforward direct API integration:

1. Search Wikipedia for the query.
2. Take the top `k` candidate pages.
3. Fetch all of those candidate pages in full.
4. Hand that retrieved content to the model.

Important detail:

- this benchmark does not count raw HTML or raw API wire payloads
- it normalizes direct page content to plain text first
- that keeps the comparison focused on retrieval strategy, not HTML cleanup

### Strategy B: Progressive MCP retrieval

This uses the MCP server's intended retrieval ladder:

1. `search_articles`
2. `get_summaries` for the top candidates
3. `get_toc` only for pages that remain plausible after scouting
4. `get_section` or `get_page` only for the final chosen targets

## Why The Deep Targets Are Predeclared

The goal of this benchmark is to isolate retrieval cost, not to benchmark an LLM's reasoning quality.

If we let a model dynamically choose targets during the benchmark, the result would mix together:

- model decision quality
- prompt quality
- retrieval strategy cost

Instead, each case predeclares the pages or sections that a careful model should eventually choose. That makes the comparison deterministic and keeps the benchmark focused on context efficiency.

## Reproducibility

Install benchmark dependencies:

```bash
cd wikipedia-mcp-server
./.venv/bin/python -m pip install -e ".[benchmark]"
```

Run the benchmark:

```bash
./.venv/bin/python scripts/benchmark_token_efficiency.py
```

Outputs:

- console: Markdown summary
- file: `benchmark_results.json`

Token counting:

- tokenizer: `o200k_base`
- both strategies are counted on the exact JSON payloads that would be handed to the model

## Benchmark Cases

### 1. Narrow question, one relevant section

Query:

```text
What molecules are produced during the light-dependent reactions of photosynthesis?
```

Intended deep target:

- `Photosynthesis` -> `Light-dependent reactions`

Why it matters:

- naive retrieval often pulls multiple full candidate pages before discovering that one section answers the question

### 2. Two relevant pages, compare without extra full-page fetches

Query:

```text
Compare photosynthesis and cellular respiration.
```

Intended deep targets:

- `Photosynthesis` -> `Introduction`
- `Cellular respiration` -> `Introduction`

Why it matters:

- some questions genuinely need multiple pages
- the benefit here is not "one section beats one page"
- the benefit is avoiding full-page fetches for extra candidate pages that turn out to be unnecessary

### 3. Broad question on one page, but only two sections are needed

Query:

```text
Explain the development and implications of general relativity.
```

Intended deep targets:

- `General relativity` -> `History`
- `General relativity` -> `Consequences of Einstein's theory`

Why it matters:

- search results include related but unnecessary pages
- the MCP ladder helps the model scout first, stay on the correct page, and fetch only the relevant sections

### 4. One page, two narrow sections

Query:

```text
Which elements exhibit superconductivity and what are their critical temperatures?
```

Intended deep targets:

- `Superconductivity` -> `Material`
- `Superconductivity` -> `Critical temperature`

Why it matters:

- the answer needs two narrow slices of one page
- naive retrieval wastes context on full-page fetches for other candidate pages

## Results Snapshot

Snapshot date:

- `2026-04-11`

Aggregate result:

- direct baseline total: `271412` tokens
- MCP total: `52943` tokens
- reduction: `218469` fewer tokens
- relative improvement: `80.49%` fewer tokens
- direct/MCP ratio: `5.13x`

Per-case summary:

| Case | Direct Tokens | MCP Tokens | Reduction | Ratio |
| --- | ---: | ---: | ---: | ---: |
| Narrow question, one relevant section | `38024` | `3722` | `90.21%` | `10.22x` |
| Two relevant pages, compare without extra full-page fetches | `40534` | `37081` | `8.52%` | `1.09x` |
| Broad question on one page, but only two sections are needed | `105695` | `9533` | `90.98%` | `11.09x` |
| One page, two narrow sections | `87159` | `2607` | `97.01%` | `33.43x` |

## What The Results Mean

The benchmark supports the intended product story:

- the biggest gains happen when the query is narrow or when search returns several plausible but mostly unnecessary candidate pages
- the MCP ladder is especially effective when the model can stop at a section instead of escalating to whole-page retrieval
- the gains are smaller when the task truly needs substantial content from multiple pages

That last point is important.

This benchmark does not claim that progressive retrieval always wins by an order of magnitude. In the `photosynthesis vs cellular respiration` comparison case, the savings are modest because the question really does need material from two pages. That is a feature of the benchmark, not a flaw: it shows the evaluation is honest rather than cherry-picked.

## Release-Ready Interpretation

A careful claim for the repository would be:

This MCP server reduces wasted context by letting models compare candidate Wikipedia pages cheaply before fetching large bodies of text. In a deterministic benchmark of four representative queries, the progressive retrieval path used `80.49%` fewer tokens overall than a naive direct-integration baseline that fetched the top candidate pages in full.

## Limitations

- The deep targets are benchmark inputs, not model outputs.
- Wikipedia search rankings can drift over time.
- Token counts depend on the tokenizer; this benchmark uses `o200k_base`.
- The direct baseline is intentionally naive. A custom client that already implements staged retrieval could narrow the gap.

Those limitations are acceptable because the benchmark is meant to justify this server's core value proposition: progressive selection before deep retrieval.
