import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfWriter

from insurance_report_extract import (
    NUMBER_PATTERN,
    extract_report,
)


class InsuranceReportExtractTests(unittest.TestCase):
    def test_number_tokens_preserve_negative_and_missing_values(self):
        text = "Net Profit (21,837,624) - 1,250.50"
        tokens = NUMBER_PATTERN.findall(text)

        self.assertIn("(21,837,624)", tokens)
        self.assertIn("-", tokens)
        self.assertIn("1,250.50", tokens)

    def test_reporting_period_match_stops_at_line_end(self):
        import re
        from insurance_report_extract import PERIOD_PATTERNS

        text = (
            "Notes to the Consolidated Financial Statements\n"
            "For the Quarter Ended Ashoj 31, 2082 "
            "(October 17, 2025)\n"
            "1. Reporting Entity\n"
        )

        matches = [
            match
            for pattern in PERIOD_PATTERNS
            for match in pattern.finditer(text)
        ]

        self.assertTrue(matches)
        self.assertTrue(
            all("Reporting Entity" not in m.group(1) for m in matches)
        )
        self.assertTrue(
            any("October 17, 2025" in m.group(1) for m in matches)
        )

    def test_extraction_preserves_page_and_unverified_status(self):
        with TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "sample.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)

            with pdf_path.open("wb") as file:
                writer.write(file)

            # Blank pages are valid PDFs but have no extractable text.
            result = extract_report(pdf_path)

            self.assertEqual(result["document"]["page_count"], 1)
            self.assertEqual(result["extraction"]["page_text"][0]["page"], 1)
            self.assertEqual(
                result["extraction"]["reporting_period"]["status"],
                "needs_manual_confirmation",
            )
            self.assertEqual(
                result["extraction"]["financial_candidates"], []
            )

    def test_real_report_candidates_keep_page_references(self):
        pdf_path = Path(
            "reports/research/source_docs/"
            "nepal_life_q1_financial_report.pdf"
        )

        if not pdf_path.exists():
            self.skipTest("Downloaded sample report is not available.")

        result = extract_report(pdf_path)
        candidates = result["extraction"]["financial_candidates"]

        self.assertGreater(len(candidates), 0)
        self.assertTrue(
            all(isinstance(item["page"], int) for item in candidates)
        )
        self.assertTrue(
            all(
                item["verification_status"] == "unverified_candidate"
                for item in candidates
            )
        )


if __name__ == "__main__":
    unittest.main()
