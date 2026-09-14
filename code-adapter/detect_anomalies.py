from pathlib import Path
import json
import pandas as pd


INCOMING_DIR = Path(__file__).parent / "incoming"


def find_sheet(report, name):
    for sheet in report["sheets"]:
        if sheet["sheet"] == name:
            return sheet
    return None


def load_table(path, sheet_info):
    raw = pd.read_excel(
        path,
        sheet_name=sheet_info["sheet"],
        header=None,
    )

    header_row = sheet_info.get("header_row")

    if header_row is None:
        return None

    headers = [
        str(value).strip() if pd.notna(value) else f"Unnamed_{i}"
        for i, value in enumerate(raw.iloc[header_row])
    ]

    data = raw.iloc[header_row + 1:].copy()
    data.columns = headers
    return data.dropna(how="all")


def numeric_column(df, keywords):
    for column in df.columns:
        name = str(column).lower()
        if any(keyword in name for keyword in keywords):
            numeric = pd.to_numeric(df[column], errors="coerce")
            if numeric.notna().sum() > 0:
                return column, numeric
    return None, None


def detect_anomalies(path, report):
    anomalies = []

    # ---------------------------------------------------------
    # 1. Duplicate identifiers discovered by the profiler
    # ---------------------------------------------------------
    for sheet in report["sheets"]:
        duplicates = sheet.get("possible_duplicate_records", {})

        for column, info in duplicates.items():
            anomalies.append({
                "type": "duplicate_identifier",
                "severity": "high",
                "sheet": sheet["sheet"],
                "column": column,
                "details": (
                    f"{info['duplicate_count']} duplicate records found. "
                    f"Values: {', '.join(info['duplicate_values'])}"
                ),
            })

    # ---------------------------------------------------------
    # 2. Numeric anomaly detection
    # ---------------------------------------------------------
    for sheet in report["sheets"]:
        if sheet.get("type") != "tabular":
            continue

        for column, summary in sheet.get("numeric_summary", {}).items():

            minimum = summary["minimum"]
            maximum = summary["maximum"]

            name = column.lower()

            if any(
                word in name
                for word in [
                    "qty",
                    "quantity",
                    "amount",
                    "cost",
                    "salary",
                    "revenue",
                    "expense",
                    "price",
                    "profit",
                    "budget",
                ]
            ):
                if minimum < 0:
                    anomalies.append({
                        "type": "negative_value",
                        "severity": "high",
                        "sheet": sheet["sheet"],
                        "column": column,
                        "details": f"Minimum value is {minimum}.",
                    })

            if "salary" in name and maximum > 300000:
                anomalies.append({
                    "type": "extreme_value",
                    "severity": "high",
                    "sheet": sheet["sheet"],
                    "column": column,
                    "details": f"Maximum salary is {maximum}.",
                })

            if "qty" in name and maximum > 1000:
                anomalies.append({
                    "type": "extreme_value",
                    "severity": "medium",
                    "sheet": sheet["sheet"],
                    "column": column,
                    "details": f"Maximum quantity is {maximum}.",
                })

    # ---------------------------------------------------------
    # 3. Financial reconciliation
    # ---------------------------------------------------------
    financial = find_sheet(report, "Financial_Summary")

    if financial:
        df = load_table(path, financial)

        if df is not None:
            revenue_col, revenue = numeric_column(
                df,
                ["gross revenue"],
            )

            expense_col, expenses = numeric_column(
                df,
                ["operating expenses"],
            )

            calc_col, calculated = numeric_column(
                df,
                ["net profit"],
            )

            ledger_col, ledger = numeric_column(
                df,
                ["reported profit", "ledger"],
            )

            if revenue is not None and expenses is not None:
                expected = revenue - expenses

                if calc_col:
                    difference = calculated - expected
                    bad = difference.abs() > 0.01

                    if bad.any():
                        anomalies.append({
                            "type": "financial_reconciliation",
                            "severity": "high",
                            "sheet": "Financial_Summary",
                            "details": (
                                f"{int(bad.sum())} rows have Net Profit "
                                f"different from Gross Revenue minus "
                                f"Operating Expenses."
                            ),
                        })

                if ledger_col and calc_col:
                    difference = calculated - ledger
                    bad = difference.abs() > 0.01

                    if bad.any():
                        anomalies.append({
                            "type": "ledger_discrepancy",
                            "severity": "high",
                            "sheet": "Financial_Summary",
                            "details": (
                                f"{int(bad.sum())} rows differ between "
                                f"calculated and reported profit."
                            ),
                        })

    # ---------------------------------------------------------
    # 4. Inventory reconciliation
    # ---------------------------------------------------------
    inventory = find_sheet(report, "Inventory_Status")

    if inventory:
        df = load_table(path, inventory)

        if df is not None:
            required = [
                "Opening_Stock",
                "Received_Qty",
                "Sold_Qty",
                "Damaged_Qty",
                "Closing_Stock",
            ]

            if all(column in df.columns for column in required):
                numeric = df[required].apply(
                    pd.to_numeric,
                    errors="coerce",
                )

                expected = (
                    numeric["Opening_Stock"]
                    + numeric["Received_Qty"]
                    - numeric["Sold_Qty"]
                    - numeric["Damaged_Qty"]
                )

                closing = numeric["Closing_Stock"]

                valid = expected.notna() & closing.notna()
                mismatch = valid & ((expected - closing).abs() > 0.01)

                if mismatch.any():
                    anomalies.append({
                        "type": "inventory_reconciliation",
                        "severity": "high",
                        "sheet": "Inventory_Status",
                        "details": (
                            f"{int(mismatch.sum())} inventory records "
                            f"have closing stock inconsistent with "
                            f"opening + received - sold - damaged."
                        ),
                    })

    # ---------------------------------------------------------
    # 5. Project budget overruns
    # ---------------------------------------------------------
    projects = find_sheet(report, "Projects_Tracker")

    if projects:
        df = load_table(path, projects)

        if df is not None:
            budget_col, budget = numeric_column(
                df,
                ["budget"],
            )

            actual_col, actual = numeric_column(
                df,
                ["actual_cost", "actual cost"],
            )

            if budget is not None and actual is not None:
                valid = budget.notna() & actual.notna()
                overruns = valid & (actual > budget)

                if overruns.any():
                    anomalies.append({
                        "type": "project_budget_overrun",
                        "severity": "high",
                        "sheet": "Projects_Tracker",
                        "details": (
                            f"{int(overruns.sum())} projects have "
                            f"actual cost above budget."
                        ),
                    })

    # ---------------------------------------------------------
    # 6. Missing-data concentration
    # ---------------------------------------------------------
    for sheet in report["sheets"]:
        if sheet.get("type") != "tabular":
            continue

        rows = sheet.get("data_rows", 0)
        missing = sheet.get("total_missing_cells", 0)
        columns = len(sheet.get("columns", []))

        if rows and columns:
            total_cells = rows * columns
            missing_ratio = missing / total_cells

            if missing_ratio >= 0.20:
                anomalies.append({
                    "type": "high_missing_data",
                    "severity": "medium",
                    "sheet": sheet["sheet"],
                    "details": (
                        f"{missing_ratio:.1%} of data cells are missing."
                    ),
                })

    return anomalies


def main():
    workbooks = sorted(INCOMING_DIR.glob("*.xlsx"))

    if not workbooks:
        print("No Excel workbook found.")
        return

    workbook = workbooks[-1]

    analysis_file = (
        INCOMING_DIR
        / f"{workbook.stem}_analysis.json"
    )

    report = json.loads(
        analysis_file.read_text(encoding="utf-8")
    )

    print("=" * 80)
    print("BUSINESS RULE / ANOMALY DETECTION")
    print("=" * 80)
    print("Workbook:", workbook.name)

    anomalies = detect_anomalies(workbook, report)

    output = {
        "file": workbook.name,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }

    output_file = (
        INCOMING_DIR
        / f"{workbook.stem}_anomalies.json"
    )

    output_file.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print("\nAnomalies found:", len(anomalies))

    for anomaly in anomalies:
        print(
            f"[{anomaly['severity'].upper()}] "
            f"{anomaly['type']} | "
            f"{anomaly['sheet']} | "
            f"{anomaly['details']}"
        )

    print("\nReport:", output_file)
    print("=" * 80)


if __name__ == "__main__":
    main()
