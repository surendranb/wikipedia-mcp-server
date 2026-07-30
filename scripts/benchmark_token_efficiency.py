from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import tiktoken

from server import (
    WikipediaClient,
    get_page,
    get_section,
    get_summaries,
    get_toc,
    search_articles,
    strip_html,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "benchmark_results.json"
ENCODING_NAME = "o200k_base"


SelectionMode = Literal["section", "page"]


@dataclass(frozen=True)
class DeepSelection:
    title: str
    mode: SelectionMode
    target: str


@dataclass(frozen=True)
class BenchmarkCase:
    slug: str
    name: str
    query: str
    candidate_limit: int
    baseline_full_pages: int
    summary_titles: int
    selections: Sequence[DeepSelection]
    expected_terms: Sequence[str]
    rationale: str


@dataclass
class PayloadStat:
    name: str
    tokens: int
    chars: int


CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        slug="photosynthesis_products",
        name="Narrow question, one relevant section",
        query="What molecules are produced during the light-dependent reactions of photosynthesis?",
        candidate_limit=5,
        baseline_full_pages=3,
        summary_titles=3,
        selections=(DeepSelection("Photosynthesis", "section", "Light-dependent reactions"),),
        expected_terms=("ATP", "NADPH", "oxygen"),
        rationale=(
            "A naive strategy often fetches several whole candidate pages before realizing one section on "
            "Photosynthesis is sufficient."
        ),
    ),
    BenchmarkCase(
        slug="photosynthesis_vs_respiration",
        name="Two relevant pages, compare without extra full-page fetches",
        query="Compare photosynthesis and cellular respiration.",
        candidate_limit=5,
        baseline_full_pages=3,
        summary_titles=3,
        selections=(
            DeepSelection("Photosynthesis", "section", "Introduction"),
            DeepSelection("Cellular respiration", "section", "Introduction"),
        ),
        expected_terms=("photosynthesis", "cellular respiration", "ATP"),
        rationale=(
            "The answer draws from two pages, but a naive top-k full-page strategy also pulls an extra third page "
            "that is not needed."
        ),
    ),
    BenchmarkCase(
        slug="general_relativity",
        name="Broad question on one page, but only two sections are needed",
        query="Explain the development and implications of general relativity.",
        candidate_limit=5,
        baseline_full_pages=3,
        summary_titles=3,
        selections=(
            DeepSelection("General relativity", "section", "History"),
            DeepSelection("General relativity", "section", "Consequences of Einstein's theory"),
        ),
        expected_terms=("Einstein", "Mercury", "black holes"),
        rationale=(
            "The top search results include nearby but unnecessary pages. Progressive retrieval can inspect "
            "candidates cheaply, stay on the right page, and fetch only the sections needed for development and implications."
        ),
    ),
    BenchmarkCase(
        slug="superconductivity",
        name="One page, two narrow sections",
        query="Which elements exhibit superconductivity and what are their critical temperatures?",
        candidate_limit=5,
        baseline_full_pages=3,
        summary_titles=3,
        selections=(
            DeepSelection("Superconductivity", "section", "Material"),
            DeepSelection("Superconductivity", "section", "Critical temperature"),
        ),
        expected_terms=("mercury", "lead", "niobium"),
        rationale=(
            "The answer requires material classes plus critical-temperature context, but not whole-page dumps for "
            "other candidate articles."
        ),
    ),
]


def to_json_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def count_tokens(encoding: tiktoken.Encoding, payload: Any) -> int:
    return len(encoding.encode(to_json_text(payload)))


def count_chars(payload: Any) -> int:
    return len(to_json_text(payload))


def summarize_direct_search(client: WikipediaClient, query: str, limit: int) -> list[dict[str, str]]:
    payload = client._get_json(
        client.ACTION_API,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": max(1, min(limit, 10)),
            "srprop": "snippet",
        },
    )
    results: list[dict[str, str]] = []
    for item in payload.get("query", {}).get("search", []):
        results.append({"title": item["title"], "snippet": strip_html(item.get("snippet", ""))})
    return results


def fetch_direct_full_page(client: WikipediaClient, title: str) -> dict[str, Any]:
    payload = client._get_json(
        client.ACTION_API,
        params={"action": "parse", "page": title, "prop": "text", "format": "json"},
    )
    html = payload.get("parse", {}).get("text", {}).get("*", "")
    return {"title": title, "text": strip_html(html)}


def contains_terms(payloads: Sequence[Any], expected_terms: Sequence[str]) -> bool:
    corpus = "\n".join(to_json_text(payload).lower() for payload in payloads)
    return all(term.lower() in corpus for term in expected_terms)


def build_direct_path(case: BenchmarkCase, client: WikipediaClient, encoding: tiktoken.Encoding) -> dict[str, Any]:
    search_payload = summarize_direct_search(client, case.query, case.candidate_limit)
    candidate_titles = [item["title"] for item in search_payload[: case.baseline_full_pages]]
    full_pages = [fetch_direct_full_page(client, title) for title in candidate_titles]
    stats = [PayloadStat("search_candidates", count_tokens(encoding, search_payload), count_chars(search_payload))]
    stats.extend(
        PayloadStat(f"full_page:{page['title']}", count_tokens(encoding, page), count_chars(page)) for page in full_pages
    )
    return {
        "strategy": "Direct Wikipedia API, naive top-k full-page retrieval",
        "candidate_titles": [item["title"] for item in search_payload[: case.summary_titles]],
        "deep_fetches": [page["title"] for page in full_pages],
        "stats": [asdict(stat) for stat in stats],
        "total_tokens": sum(stat.tokens for stat in stats),
        "total_chars": sum(stat.chars for stat in stats),
        "pages_fetched": len(full_pages),
        "sections_fetched": 0,
        "contains_expected_terms": contains_terms(full_pages, case.expected_terms),
    }


def build_mcp_path(case: BenchmarkCase, encoding: tiktoken.Encoding) -> dict[str, Any]:
    search_payload = json.loads(search_articles(case.query, limit=case.candidate_limit))
    candidate_titles = [item["title"] for item in search_payload[: case.summary_titles]]
    summaries_payload = json.loads(get_summaries(candidate_titles))

    toc_titles: list[str] = []
    for selection in case.selections:
        if selection.title not in toc_titles:
            toc_titles.append(selection.title)
    tocs = {title: json.loads(get_toc(title)) for title in toc_titles}

    deep_payloads: list[dict[str, Any]] = []
    for selection in case.selections:
        if selection.mode == "section":
            deep_payloads.append(json.loads(get_section(selection.title, selection.target)))
        else:
            deep_payloads.append(json.loads(get_page(selection.title)))

    stats = [
        PayloadStat("search_articles", count_tokens(encoding, search_payload), count_chars(search_payload)),
        PayloadStat("get_summaries", count_tokens(encoding, summaries_payload), count_chars(summaries_payload)),
    ]
    stats.extend(PayloadStat(f"get_toc:{title}", count_tokens(encoding, toc), count_chars(toc)) for title, toc in tocs.items())
    stats.extend(
        PayloadStat(
            f"{'get_section' if selection.mode == 'section' else 'get_page'}:{selection.title}:{selection.target}",
            count_tokens(encoding, payload),
            count_chars(payload),
        )
        for selection, payload in zip(case.selections, deep_payloads)
    )
    return {
        "strategy": "Wikipedia MCP progressive retrieval",
        "candidate_titles": candidate_titles,
        "deep_fetches": [
            {
                "title": selection.title,
                "mode": selection.mode,
                "target": selection.target,
            }
            for selection in case.selections
        ],
        "stats": [asdict(stat) for stat in stats],
        "total_tokens": sum(stat.tokens for stat in stats),
        "total_chars": sum(stat.chars for stat in stats),
        "pages_fetched": sum(1 for selection in case.selections if selection.mode == "page"),
        "sections_fetched": sum(1 for selection in case.selections if selection.mode == "section"),
        "contains_expected_terms": contains_terms(deep_payloads, case.expected_terms),
    }


def benchmark_case(case: BenchmarkCase, client: WikipediaClient, encoding: tiktoken.Encoding) -> dict[str, Any]:
    direct = build_direct_path(case, client, encoding)
    mcp = build_mcp_path(case, encoding)
    token_delta = direct["total_tokens"] - mcp["total_tokens"]
    return {
        "slug": case.slug,
        "name": case.name,
        "query": case.query,
        "rationale": case.rationale,
        "expected_terms": list(case.expected_terms),
        "direct": direct,
        "mcp": mcp,
        "comparison": {
            "token_delta": token_delta,
            "token_reduction_pct": (token_delta / direct["total_tokens"]) * 100 if direct["total_tokens"] else 0.0,
            "direct_to_mcp_ratio": direct["total_tokens"] / mcp["total_tokens"] if mcp["total_tokens"] else None,
        },
    }


def render_markdown(results: Sequence[dict[str, Any]]) -> str:
    direct_total = sum(item["direct"]["total_tokens"] for item in results)
    mcp_total = sum(item["mcp"]["total_tokens"] for item in results)
    token_delta = direct_total - mcp_total
    reduction = (token_delta / direct_total) * 100 if direct_total else 0.0
    lines: list[str] = []
    lines.append("# Token Efficiency Benchmark Results")
    lines.append("")
    lines.append(f"Tokenizer: `{ENCODING_NAME}`")
    lines.append("")
    lines.append("## Aggregate")
    lines.append(f"- direct baseline total: `{direct_total}` tokens")
    lines.append(f"- MCP total: `{mcp_total}` tokens")
    lines.append(f"- reduction: `{token_delta}` fewer tokens")
    lines.append(f"- relative improvement: `{reduction:.2f}%` fewer tokens")
    lines.append(f"- direct/MCP ratio: `{direct_total / mcp_total:.2f}x`")
    lines.append("")
    lines.append("## Per Case")
    for item in results:
        lines.append(f"### {item['name']}")
        lines.append(f"- query: `{item['query']}`")
        lines.append(f"- rationale: {item['rationale']}")
        lines.append(f"- direct tokens: `{item['direct']['total_tokens']}`")
        lines.append(f"- MCP tokens: `{item['mcp']['total_tokens']}`")
        lines.append(f"- reduction: `{item['comparison']['token_reduction_pct']:.2f}%`")
        lines.append(f"- direct/MCP ratio: `{item['comparison']['direct_to_mcp_ratio']:.2f}x`")
        lines.append(f"- direct deep fetches: `{item['direct']['deep_fetches']}`")
        lines.append(f"- MCP deep fetches: `{item['mcp']['deep_fetches']}`")
        lines.append(f"- expected terms covered by direct path: `{item['direct']['contains_expected_terms']}`")
        lines.append(f"- expected terms covered by MCP path: `{item['mcp']['contains_expected_terms']}`")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    client = WikipediaClient()
    results = [benchmark_case(case, client, encoding) for case in CASES]
    payload = {"tokenizer": ENCODING_NAME, "results": results}
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render_markdown(results))


if __name__ == "__main__":
    main()
