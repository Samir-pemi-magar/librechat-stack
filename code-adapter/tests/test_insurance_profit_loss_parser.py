import unittest
from pathlib import Path

from pypdf import PdfReader

from insurance_statement_parser import parse_profit_or_loss


class InsuranceProfitLossParserTests(unittest.TestCase):
    def test_eight_columns_are_mapped_explicitly(self):
        lines = [
            "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS",
            "Gross Earned Premiums 13,503,857,311 13,503,857,311 "
            "11,968,967,002 11,968,967,002 13,503,857,311 "
            "13,503,857,311 11,968,967,002 11,968,967,002",
            "CONDENSED CONSOLIDATED STATEMENT OF OTHER COMPREHENSIVE INCOME",
        ]

        records = parse_profit_or_loss(lines)

        self.assertEqual(len(records), 8)
        self.assertEqual(records[0]["entity"], "Group")
        self.assertEqual(
            records[0]["period_label"], "Current year - This Quarter"
        )
        self.assertEqual(records[1]["period_label"], "Current year - YTD")
        self.assertEqual(
            records[4]["entity"], "Insurance Company"
        )
        self.assertEqual(
            records[7]["period_label"],
            "Corresponding previous year - YTD",
        )
        self.assertEqual(records[0]["value"], 13503857311)
        self.assertTrue(
            all(r["verification_status"] == "parsed_unverified" for r in records)
        )

    def test_parenthesized_values_remain_negative(self):
        lines = [
            "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS",
            "Premiums Ceded (134,650,000) (134,650,000) "
            "(156,997,192) (156,997,192) (134,650,000) "
            "(134,650,000) (156,997,192) (156,997,192)",
            "CONDENSED CONSOLIDATED STATEMENT OF OTHER COMPREHENSIVE INCOME",
        ]

        records = parse_profit_or_loss(lines)
        self.assertEqual(len(records), 8)
        self.assertTrue(all(r["value"] < 0 for r in records))

    def test_malformed_merged_values_are_not_guessed(self):
        lines = [
            "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS",
            "Total Expenses 1 2 3 4 5 6 1657046036616570460366",
            "CONDENSED CONSOLIDATED STATEMENT OF OTHER COMPREHENSIVE INCOME",
        ]

        self.assertEqual(parse_profit_or_loss(lines), [])

    def test_real_report_known_rows(self):
        pdf_path = Path(
            "reports/research/source_docs/"
            "nepal_life_q1_financial_report.pdf"
        )
        if not pdf_path.exists():
            self.skipTest("Downloaded report is not available.")

        reader = PdfReader(str(pdf_path))
        lines = [
            line.strip()
            for line in (reader.pages[0].extract_text() or "").splitlines()
            if line.strip()
        ]
        records = parse_profit_or_loss(lines, page_number=1)

        premium = [
            r for r in records if r["metric"] == "Gross Earned Premiums"
        ]
        self.assertEqual(len(premium), 8)
        self.assertEqual(premium[0]["value"], 13503857311)
        self.assertEqual(premium[2]["value"], 11968967002)
        self.assertEqual(premium[4]["entity"], "Insurance Company")
        self.assertTrue(all(r["source_page"] == 1 for r in premium))

        ceded = [r for r in records if r["metric"] == "Premiums Ceded"]
        self.assertEqual(len(ceded), 8)
        self.assertEqual(ceded[0]["value"], -134650000)

        expenses = [
            r for r in records if r["metric"] == "Total Expenses"
        ]
        self.assertEqual(len(expenses), 8)
        self.assertEqual(
            [r["value"] for r in expenses],
            [
                17296813441,
                17296813441,
                16575337658,
                16575337658,
                17283742001,
                17283742001,
                16570460366,
                16570460366,
            ],
        )


if __name__ == "__main__":
    unittest.main()
