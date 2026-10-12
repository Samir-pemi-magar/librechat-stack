import unittest

from industry_profile import profile_industry


class IndustryProfileTests(unittest.TestCase):
    def test_general_finance_workbook(self):
        analysis = {
            "file": "company.xlsx",
            "sheets": [{
                "sheet": "Financial_Summary",
                "type": "tabular",
                "data_rows": 10,
                "columns": [
                    "Gross Revenue",
                    "Operating Expenses",
                    "Net Profit (Calc)",
                    "Reported Profit (Ledger)",
                ],
            }],
        }

        result = profile_industry(analysis)

        self.assertEqual(result["detected_industry"], "general_finance")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["insurance_metric_columns"], {})

    def test_insurance_workbook(self):
        analysis = {
            "file": "insurance.xlsx",
            "sheets": [{
                "sheet": "Claims",
                "type": "tabular",
                "data_rows": 20,
                "columns": [
                    "Policy Number",
                    "Written Premium",
                    "Claims Paid",
                    "Loss Ratio",
                    "Solvency Ratio",
                ],
            }],
        }

        result = profile_industry(analysis)

        self.assertEqual(result["detected_industry"], "insurance")
        self.assertIn("premiums", result["insurance_metric_columns"])
        self.assertIn("claims", result["insurance_metric_columns"])
        self.assertIn("claims_ratio", result["insurance_metric_columns"])
        self.assertIn("solvency", result["insurance_metric_columns"])

    def test_unstructured_sheets_are_not_classified_from_columns(self):
        analysis = {
            "file": "notes.xlsx",
            "sheets": [{
                "sheet": "Notes",
                "type": "unstructured",
                "columns": [],
            }],
        }

        result = profile_industry(analysis)

        self.assertEqual(result["detected_industry"], "general")
        self.assertEqual(result["confidence"], "low")

    def test_tied_industry_scores_have_low_confidence(self):
        analysis = {
            "file": "mixed.xlsx",
            "sheets": [{
                "sheet": "Mixed",
                "type": "tabular",
                "columns": ["SKU", "Gross Revenue"],
            }],
        }

        result = profile_industry(analysis)

        self.assertEqual(result["confidence"], "low")

    def test_store_inside_long_identifier_does_not_classify_retail(self):
        analysis = {
            "file": "customers.xlsx",
            "sheets": [{
                "sheet": "Customers",
                "type": "tabular",
                "columns": ["customer_store_code", "Customer Name"],
            }],
        }
        result = profile_industry(analysis)
        self.assertNotIn("retail", result["industry_scores"])

    def test_close_mixed_industry_scores_have_low_confidence(self):
        analysis = {
            "file": "mixed_finance.xlsx",
            "sheets": [{
                "sheet": "Summary",
                "type": "tabular",
                "columns": ["Written Premium", "Claims Paid", "Net Profit"],
            }],
        }
        result = profile_industry(analysis)
        self.assertEqual(result["detected_industry"], "insurance")
        self.assertEqual(result["confidence"], "low")


if __name__ == "__main__":
    unittest.main()
