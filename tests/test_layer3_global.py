"""Global-readiness regressions.

This module researches property in any country. Each test below pins a place
where the code previously assumed one country, one currency, one script or one
character encoding, and silently produced a wrong result rather than an error.
"""

import socket
import unittest
import urllib.request
from unittest.mock import MagicMock, patch


class GlobalReadinessTests(unittest.TestCase):
    def test_slug_survives_every_writing_system(self):
        from ML.deep_research.layer2.fs import slug

        self.assertEqual(slug("Bauträger-Risiko"), "bautrager-risiko")
        self.assertEqual(slug("Marché & valorisation"), "marche-and-valorisation")
        for name in ("建筑条件", "Экономика", "التخطيط"):
            value = slug(name)
            self.assertTrue(value, name)
            self.assertTrue(value.isascii(), name)
        # ASCII roster slugs must be byte-identical, so Layer 2 output is unchanged.
        self.assertEqual(
            slug("Building condition, capital expenditure & warranty"),
            "building-condition-capital-expenditure-and-warranty",
        )

    def test_pages_decode_by_declared_encoding_and_tables_keep_cells(self):
        from ML.deep_research.layer3.text_extraction import canonical_text

        cases = [
            ("shift-jis", "text/html; charset=Shift_JIS", "東京都"),
            ("big5", "text/html; charset=big5", "台北市"),
            ("windows-1251", "text/html; charset=windows-1251", "Аренда"),
            ("iso-8859-7", "text/html; charset=iso-8859-7", "Ενέργεια"),
        ]
        for codec, content_type, word in cases:
            body = f"<html><body><p>{word}</p></body></html>".encode(codec)
            self.assertIn(word, canonical_text(body, content_type), codec)
        table = b"<table><tr><td>Unit 1</td><td>1,200</td></tr></table>"
        self.assertIn("Unit 1 | 1,200", canonical_text(table, "text/html"))

    def test_source_urls_must_be_public_http_without_credentials(self):
        from ML.deep_research.layer3.retrieval import validate_public_url

        for url in (
            "file:///etc/passwd",
            "https://user:password@example.com/report",
            "https://example.com:wrong/report",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_public_url(url)

        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch("socket.getaddrinfo", return_value=private):
            with self.assertRaisesRegex(ValueError, "non-public"):
                validate_public_url("https://example.com/report")

    def test_redirect_targets_are_revalidated(self):
        from ML.deep_research.layer3.providers.openai_search import _SafeRedirectHandler

        expected = MagicMock()
        with (
            patch(
                "ML.deep_research.layer3.providers.openai_search.validate_public_url"
            ) as validate,
            patch.object(
                urllib.request.HTTPRedirectHandler,
                "redirect_request",
                return_value=expected,
            ),
        ):
            actual = _SafeRedirectHandler().redirect_request(
                urllib.request.Request("https://public.example/start"),
                None,
                302,
                "Found",
                {},
                "http://127.0.0.1/private",
            )

        validate.assert_called_once_with("http://127.0.0.1/private")
        self.assertIs(actual, expected)

    def test_fetch_rejects_declared_and_streamed_oversize_sources(self):
        from ML.deep_research.layer3.providers.openai_search import _fetch

        for declared, body in (("11", b""), (None, b"x" * 11)):
            response = MagicMock()
            response.geturl.return_value = "https://public.example/report"
            response.headers.get.side_effect = lambda name, default="": {
                "Content-Length": declared,
                "Last-Modified": "",
            }.get(name, default)
            response.read.return_value = body
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value = response
            with (
                self.subTest(declared=declared),
                patch(
                    "ML.deep_research.layer3.providers.openai_search.validate_public_url",
                    side_effect=lambda url: url,
                ),
                patch(
                    "ML.deep_research.layer3.providers.openai_search.urllib.request.build_opener",
                    return_value=opener,
                ),
                patch(
                    "ML.deep_research.layer3.providers.openai_search.MAX_SOURCE_BYTES",
                    10,
                ),
                self.assertRaisesRegex(ValueError, "10 bytes"),
            ):
                _fetch("https://public.example/report")


if __name__ == "__main__":
    unittest.main()
