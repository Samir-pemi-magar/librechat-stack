import unittest

from market_research import build_insurance_queries, classify_domain


class MarketResearchTests(unittest.TestCase):
    def test_regulator_domain_candidate(self):
        self.assertEqual(
            classify_domain("https://nia.gov.np/annual-reports"),
            "insurance_regulator_domain_candidate",
        )

    def test_company_domain_candidate(self):
        self.assertEqual(
            classify_domain("https://example.com.np/annual-report"),
            "company_domain_candidate",
        )

    def test_other_domain(self):
        self.assertEqual(
            classify_domain("https://example.org/report"),
            "other_domain",
        )

    def test_default_queries_include_regulator_and_comparisons(self):
        queries = build_insurance_queries()

        self.assertEqual(len(queries), 3)
        self.assertTrue(any("Insurance Authority" in q for q in queries))
        self.assertTrue(any("annual report" in q for q in queries))

    def test_company_query_is_included(self):
        queries = build_insurance_queries(company="Example Insurance")

        self.assertEqual(len(queries), 3)
        self.assertTrue(any("Example Insurance" in q for q in queries))


if __name__ == "__main__":
    unittest.main()
