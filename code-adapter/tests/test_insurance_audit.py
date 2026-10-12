import unittest

from audit_insurance_report import (
    EXPECTED_COLUMNS,
    find_incomplete_metric_rows,
)


def make_records(statement, count, metric="Sample metric"):
    return [
        {
            "statement": statement,
            "section": "Sample section",
            "metric": metric,
            "source_page": 1,
            "entity": f"Entity {index}",
            "period_label": f"Period {index}",
            "source_text": f"{metric} source row",
        }
        for index in range(count)
    ]


class InsuranceAuditTests(unittest.TestCase):
    def test_expected_column_counts_cover_all_statements(self):
        self.assertEqual(
            EXPECTED_COLUMNS,
            {
                "Condensed Consolidated Statement of Financial Position": 4,
                "Condensed Consolidated Statement of Profit or Loss": 8,
                "Consolidated Statement of Cash Flows": 4,
            },
        )

    def test_complete_rows_pass_for_each_statement(self):
        records = []
        for statement, expected in EXPECTED_COLUMNS.items():
            records.extend(make_records(statement, expected))

        self.assertEqual(find_incomplete_metric_rows(records), [])

    def test_incomplete_four_and_eight_column_rows_are_reported(self):
        cases = (
            ("Condensed Consolidated Statement of Financial Position", 3, 4),
            ("Condensed Consolidated Statement of Profit or Loss", 7, 8),
            ("Consolidated Statement of Cash Flows", 3, 4),
        )

        for statement, actual, expected in cases:
            with self.subTest(statement=statement):
                findings = find_incomplete_metric_rows(
                    make_records(statement, actual)
                )
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["expected_values"], expected)
                self.assertEqual(findings[0]["actual_values"], actual)

    def test_unknown_statement_is_not_silently_assigned_a_column_count(self):
        records = make_records("Unknown statement", 2)
        self.assertEqual(find_incomplete_metric_rows(records), [])

    def test_same_metric_on_different_pages_is_checked_separately(self):
        records = make_records(
            "Consolidated Statement of Cash Flows", 4, "Repeated metric"
        )
        second_page = make_records(
            "Consolidated Statement of Cash Flows", 3, "Repeated metric"
        )
        for record in second_page:
            record["source_page"] = 2

        findings = find_incomplete_metric_rows(records + second_page)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["key"][-1], 2)
        self.assertEqual(findings[0]["actual_values"], 3)


if __name__ == "__main__":
    unittest.main()
