import tempfile
import unittest

from fpf_http import fetch_page_result, is_blocked_content


class FpfHttpTests(unittest.TestCase):
    def test_is_blocked_content_detects_security_page(self):
        self.assertTrue(is_blocked_content("Just a moment... Performing security verification"))
        self.assertFalse(is_blocked_content("<html><body>ok</body></html>"))

    def test_fetch_page_result_reads_from_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_key = "cached_page"
            cache_path = f"{temp_dir}/{cache_key}.html"
            with open(cache_path, "w", encoding="utf-8") as handle:
                handle.write("<html><body>cached</body></html>")

            result = fetch_page_result(
                "https://example.test/page",
                cache_dir=temp_dir,
                use_cache=True,
                cache_key=cache_key,
            )

            self.assertTrue(result.ok)
            self.assertTrue(result.cache_used)
            self.assertEqual(result.attempts, 0)
            self.assertEqual(result.content, "<html><body>cached</body></html>")


if __name__ == "__main__":
    unittest.main()
