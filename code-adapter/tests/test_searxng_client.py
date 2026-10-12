import unittest
from unittest.mock import Mock, patch

import requests

from searxng_client import SearXNGError, search_web


class SearXNGClientTests(unittest.TestCase):
    @patch("searxng_client.requests.get")
    def test_normalizes_results_and_removes_duplicates(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com/report",
                    "title": " Annual report ",
                    "content": " Financial results ",
                    "publishedDate": "2025-10-01",
                    "engines": ["test-engine"],
                },
                {
                    "url": "https://example.com/report",
                    "title": "Duplicate",
                },
                {
                    "url": "javascript:alert(1)",
                    "title": "Invalid URL",
                },
            ]
        }
        mock_get.return_value = response

        result = search_web(" insurance report ", max_results=5)

        self.assertEqual(result["query"], "insurance report")
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["results"][0]["title"], "Annual report")
        self.assertEqual(
            result["results"][0]["snippet"], "Financial results"
        )
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["timeout"], 20)
        self.assertNotIn("verify", mock_get.call_args.kwargs)

    @patch("searxng_client.requests.get")
    def test_rejects_non_dictionary_json_payload(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = ["not", "an", "object"]
        mock_get.return_value = response

        with self.assertRaises(SearXNGError):
            search_web("insurance report")

    @patch("searxng_client.requests.get")
    def test_rejects_non_dictionary_result_payload(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": ["not an object"]}
        mock_get.return_value = response

        with self.assertRaises(SearXNGError):
            search_web("insurance report")

    @patch("searxng_client.requests.get")
    def test_wraps_http_failures(self, mock_get):
        mock_get.side_effect = requests.Timeout("request timed out")

        with self.assertRaises(SearXNGError):
            search_web("insurance report")

    def test_rejects_empty_query_and_invalid_result_limit(self):
        with self.assertRaises(ValueError):
            search_web("   ")

        with self.assertRaises(ValueError):
            search_web("insurance report", max_results=21)


if __name__ == "__main__":
    unittest.main()
