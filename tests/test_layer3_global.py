"""Global-readiness regressions.

This module researches property in any country. Each test below pins a place
where the code previously assumed one country, one currency, one script or one
character encoding, and silently produced a wrong result rather than an error.
"""

import unittest


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

    def test_python_runs_as_written_and_output_is_not_clipped(self):
        from ML.deep_research.layer3.calculation_tool import run_python_code

        result = run_python_code("print(round(702668.06 * 1.19, 2))")
        self.assertTrue(result.ok)
        self.assertIn("836174.99", result.stdout)

        # Nothing is imported away, and nothing truncates what comes back.
        long_output = run_python_code("print('x' * 100000)")
        self.assertTrue(long_output.ok)
        self.assertGreaterEqual(len(long_output.stdout), 100000)
        self.assertNotIn("truncated", long_output.stdout)


if __name__ == "__main__":
    unittest.main()
