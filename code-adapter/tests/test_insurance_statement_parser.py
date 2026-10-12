import unittest
from pathlib import Path

from pypdf import PdfReader

from insurance_statement_parser import (
    parse_financial_position,
    parse_value,
)


class InsuranceStatementParserTests(unittest.TestCase):
    def test_numeric_and_missing_values(self):
        self.assertEqual(
            parse_value("199,277,985,832"),
            (199277985832, "numeric_unverified"),
        )
        self.assertEqual(
            parse_value("(21,837,624)"),
            (-21837624, "numeric_unverified"),
        )
        self.assertEqual(
            parse_value("-"),
            (None, "reported_dash"),
        )

    def test_four_columns_map_to_expected_entities_and_periods(self):
        lines = [
            "CONDENSED CONSOLIDATED STATEMENT OF FINANCIAL POSITION",
            "Particulars",
            "Group Insurance",
            "At the end of this Quarter At the end of Immediate Previous Year",
            "Investments 199,277,985,832 190,702,144,392 197,991,243,829 189,575,282,150",
            "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS",
            "Gross Earned Premiums 1 2 3 4",
        ]

        records = parse_financial_position(lines)
        investments = [r for r in records if r["metric"] == "Investments"]

        self.assertEqual(len(investments), 4)
        self.assertEqual(
            [(r["entity"], r["period_label"], r["value"]) for r in investments],
            [
                ("Group", "At the end of this Quarter", 199277985832),
                ("Group", "At the end of Immediate Previous Year", 190702144392),
                ("Insurance Company", "At the end of this Quarter", 197991243829),
                ("Insurance Company", "At the end of Immediate Previous Year", 189575282150),
            ],
        )
        self.assertTrue(
            all(r["verification_status"] == "parsed_unverified" for r in records)
        )

    def test_real_report_total_assets_and_investments(self):
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
        records = parse_financial_position(lines, page_number=1)

        assets = [r for r in records if r["metric"] == "Total Assets"]
        self.assertEqual(len(assets), 4)
        self.assertEqual(assets[0]["value"], 262336141985)
        self.assertEqual(assets[2]["value"], 262132838148)
        self.assertTrue(all(r["source_page"] == 1 for r in assets))

        investments = [r for r in records if r["metric"] == "Investments"]
        self.assertEqual(len(investments), 4)
        self.assertEqual(investments[0]["value"], 199277985832)
        self.assertEqual(investments[3]["value"], 189575282150)

    def test_dash_is_not_converted_to_zero(self):
        lines = [
            "CONDENSED CONSOLIDATED STATEMENT OF FINANCIAL POSITION",
            "Deferred Tax Assets - - - -",
            "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS",
        ]

        records = parse_financial_position(lines)
        self.assertEqual(len(records), 4)
        self.assertTrue(all(r["value"] is None for r in records))
        self.assertTrue(
            all(r["value_status"] == "reported_dash" for r in records)
        )


if __name__ == "__main__":
    unittest.main()
