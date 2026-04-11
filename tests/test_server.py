from __future__ import annotations

import unittest
from unittest.mock import patch

from server import WikipediaClient, strip_html, title_key


class UtilityTests(unittest.TestCase):
    def test_strip_html_compacts_markup(self) -> None:
        html = "<div><p>Hello <b>world</b></p><script>ignore()</script><p>Next</p></div>"
        self.assertEqual(strip_html(html), "Hello world\n\nNext")

    def test_title_key_replaces_spaces(self) -> None:
        self.assertEqual(title_key("General relativity"), "General_relativity")


class SectionResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = WikipediaClient()
        self.toc = [
            {"index": "0", "line": "Introduction", "anchor": "Introduction"},
            {"index": "1", "line": "Overview", "anchor": "Overview"},
            {"index": "3", "line": "Light-dependent reactions", "anchor": "Light-dependent_reactions"},
        ]

    def test_resolve_section_index_by_numeric_index(self) -> None:
        self.assertEqual(self.client._resolve_section_index(self.toc, "3"), "3")

    def test_resolve_section_index_by_title(self) -> None:
        self.assertEqual(self.client._resolve_section_index(self.toc, "Light-dependent reactions"), "3")

    def test_resolve_section_index_raises_for_missing_section(self) -> None:
        with self.assertRaises(ValueError):
            self.client._resolve_section_index(self.toc, "Missing")


class ClientBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = WikipediaClient()

    def test_search_articles_strips_snippet_html(self) -> None:
        payload = {
            "query": {
                "search": [
                    {"title": "Photosynthesis", "snippet": "Light <span>dependent</span> reactions"},
                ]
            }
        }
        with patch.object(self.client, "_get_json", return_value=payload):
            result = self.client.search_articles("photosynthesis", limit=3)
        self.assertEqual(result, [{"title": "Photosynthesis", "snippet": "Light dependent reactions"}])

    def test_get_toc_includes_introduction(self) -> None:
        payload = {
            "parse": {
                "sections": [
                    {"index": "1", "line": "Overview", "anchor": "Overview"},
                    {"index": "2", "line": "History", "anchor": "History"},
                ]
            }
        }
        with patch.object(self.client, "_get_json", return_value=payload):
            toc = self.client.get_toc("Example")
        self.assertEqual(toc[0]["line"], "Introduction")
        self.assertEqual(toc[1]["line"], "Overview")

    def test_get_section_returns_plain_text(self) -> None:
        toc_payload = {
            "parse": {
                "sections": [
                    {"index": "3", "line": "Light-dependent reactions", "anchor": "Light-dependent_reactions"},
                ]
            }
        }
        text_payload = {
            "parse": {
                "text": {
                    "*": "<p>ATP and NADPH are produced.</p><p>Oxygen is released.</p>"
                }
            }
        }
        with patch.object(self.client, "_get_json", side_effect=[toc_payload, text_payload]):
            result = self.client.get_section("Photosynthesis", "Light-dependent reactions")
        self.assertEqual(result["section"], "Light-dependent reactions")
        self.assertIn("ATP and NADPH are produced.", result["text"])
        self.assertIn("Oxygen is released.", result["text"])

    def test_get_page_uses_parse_fallback_when_rest_fails(self) -> None:
        with patch.object(self.client, "_get_text", side_effect=RuntimeError("rest unavailable")):
            with patch.object(
                self.client,
                "_get_json",
                return_value={"parse": {"text": {"*": "<p>Fallback page body</p>"}}},
            ):
                result = self.client.get_page("Fallback")
        self.assertEqual(result["title"], "Fallback")
        self.assertEqual(result["text"], "Fallback page body")


if __name__ == "__main__":
    unittest.main()
