import unittest
from pathlib import Path

from pypdf import PdfReader

from insurance_statement_parser import parse_cash_flow


PDF_PATH = Path(
    "reports/research/source_docs/"
    "nepal_life_q1_financial_report.pdf"
)


class InsuranceCashFlowParserTests(unittest.TestCase):
    def test_four_columns_are_mapped_explicitly(self):
        lines = [
            "Net Increase/(Decrease) In Cash & Cash Equivalents "
            "[1+2+3] 5,704,752,858 3,993,245,477 "
            "5,300,803,905 3,983,409,284",
        ]

        records = parse_cash_flow(lines, page_number=7)

        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]["entity"], "Group")
        self.assertEqual(records[0]["period_label"], "Current Year")
        self.assertEqual(records[1]["period_label"], "Previous Year")
        self.assertEqual(
            records[2]["entity"], "Insurance Company"
        )
        self.assertEqual(records[3]["period_label"], "Previous Year")
        self.assertEqual(records[0]["value"], 5704752858)
        self.assertIn("[1+2+3]", records[0]["metric"])

    def test_negative_and_missing_values_are_preserved(self):
        lines = [
            "Gross Benefits and Claims Paid "
            "(4,150,215,757) (19,196,455,466) "
            "(4,150,215,757) (19,196,455,466)",
            "Commission Received - 54,714,993 - 54,714,993",
        ]

        records = parse_cash_flow(lines)

        claims = records[:4]
        commissions = records[4:]

        self.assertTrue(all(r["value"] < 0 for r in claims))
        self.assertEqual(commissions[0]["value"], None)
        self.assertEqual(commissions[0]["value_status"], "reported_dash")
        self.assertEqual(commissions[1]["value"], 54714993)

    def test_malformed_value_row_is_rejected(self):
        lines = [
            "Ambiguous Row 1 2 3 1657046036616570460366",
        ]

        self.assertEqual(parse_cash_flow(lines), [])


    def test_reconciliation_rows_have_their_own_section(self):
        lines = [
            "Cash Flow From Financing Activities",
            "Total Cash Flow From Financing Activities [3] "
            "- (907,196,304) - (907,196,304)",
            "Net Increase/(Decrease) In Cash & Cash Equivalents "
            "[1+2+3] 5,704,752,858 3,993,245,477 "
            "5,300,803,905 3,983,409,284",
            "Cash & Cash Equivalents At Beginning of The Year/Period "
            "11,707,366,442 7,714,120,966 "
            "11,604,013,587 7,620,604,303",
            "Cash & Cash Equivalents At End of The Year/Period "
            "17,412,119,300 11,707,366,442 "
            "16,904,817,492 11,604,013,587",
        ]

        records = parse_cash_flow(lines, page_number=7)
        financing = [
            r for r in records
            if r["metric"] == "Total Cash Flow From Financing Activities [3]"
        ]
        reconciliation = [
            r for r in records
            if r["metric"].startswith((
                "Net Increase/(Decrease) In Cash & Cash Equivalents",
                "Cash & Cash Equivalents At Beginning",
                "Cash & Cash Equivalents At End",
            ))
        ]

        self.assertEqual(len(financing), 4)
        self.assertTrue(all(
            r["section"] == "Financing Activities" for r in financing
        ))
        self.assertEqual(len(reconciliation), 12)
        self.assertTrue(all(
            r["section"] == "Cash and Cash Equivalents Reconciliation"
            for r in reconciliation
        ))
        self.assertTrue(all(r["source_page"] == 7 for r in records))

    def test_reconciliation_dash_is_still_missing_not_zero(self):
        records = parse_cash_flow([
            "Cash Flow From Financing Activities",
            "Net Increase/(Decrease) In Cash & Cash Equivalents "
            "- 10 20 30",
        ])

        self.assertEqual(records[0]["section"],
                         "Cash and Cash Equivalents Reconciliation")
        self.assertIsNone(records[0]["value"])
        self.assertEqual(records[0]["value_status"], "reported_dash")

    def test_real_report_key_rows(self):
        if not PDF_PATH.exists():
            self.skipTest("Downloaded report is not available.")

        reader = PdfReader(str(PDF_PATH))
        all_records = []

        for page_index in (5, 6):
            lines = [
                line.strip()
                for line in (
                    reader.pages[page_index].extract_text() or ""
                ).splitlines()
                if line.strip()
            ]
            all_records.extend(
                parse_cash_flow(lines, page_number=page_index + 1)
            )

        operating = [
            r for r in all_records
            if r["metric"] == "Net Cash Flow From Operating Activities [1]"
        ]
        self.assertEqual(len(operating), 4)
        self.assertEqual(
            [r["value"] for r in operating],
            [
                10800288061,
                13374880662,
                10238248390,
                13884488229,
            ],
        )
        self.assertTrue(all(r["source_page"] == 6 for r in operating))

        closing_cash = [
            r for r in all_records
            if r["metric"]
            == "Cash & Cash Equivalents At End of The Year/Period"
        ]
        self.assertEqual(len(closing_cash), 4)
        self.assertEqual(
            [r["value"] for r in closing_cash],
            [
                17412119300,
                11707366442,
                16904817492,
                11604013587,
            ],
        )
        self.assertTrue(all(r["source_page"] == 7 for r in closing_cash))


if __name__ == "__main__":
    unittest.main()
