from pathlib import Path
import json
import re
import pandas as pd


INCOMING_DIR = Path(__file__).parent / "incoming"


def find_header_row(raw, max_rows=15):
    best_row = None
    best_score = -1

    for i in range(min(max_rows, len(raw))):
        values = [
            str(v).strip()
            for v in raw.iloc[i].tolist()
            if pd.notna(v) and str(v).strip()
        ]

        if len(values) < 2:
            continue

        text_count = sum(
            not re.fullmatch(r"[-+]?\d*\.?\d+", value)
            for value in values
        )

        unique_count = len(set(values))

        score = len(values) + text_count + unique_count * 0.25

        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def clean_column_name(value, index):
    if pd.isna(value) or not str(value).strip():
        return f"Unnamed_{index}"

    return str(value).strip()


def find_identifier_columns(columns):
    patterns = [
        r"^id$",
        r"[_ ]id$",
        r"^invoice[_ ]?id$",
        r"^emp[_ ]?id$",
        r"^employee[_ ]?id$",
        r"^customer[_ ]?id$",
        r"^cust[_ ]?id$",
        r"^project[_ ]?id$",
        r"^expense[_ ]?id$",
        r"^record[_ ]?id$",
    ]

    result = []

    for column in columns:
        name = str(column).strip().lower()

        if any(re.search(pattern, name) for pattern in patterns):
            result.append(column)

    return result


def convert_obvious_types(df):
    result = df.copy()

    for column in result.columns:
        series = result[column]

        if series.dtype == "object":
            cleaned = (
                series.astype(str)
                .str.strip()
                .str.replace(",", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace("%", "", regex=False)
            )

            numeric = pd.to_numeric(cleaned, errors="coerce")

            non_empty = series.notna().sum()

            if non_empty > 0 and numeric.notna().sum() / non_empty >= 0.8:
                result[column] = numeric
                continue

            date_values = pd.to_datetime(
                series,
                errors="coerce",
            )

            if non_empty > 0 and date_values.notna().sum() / non_empty >= 0.8:
                result[column] = date_values

    return result


def analyze_sheet(path, sheet_name):
    raw = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=None,
    )

    result = {
        "sheet": sheet_name,
        "raw_rows": int(len(raw)),
        "raw_columns": int(len(raw.columns)),
    }

    header_row = find_header_row(raw)

    if header_row is None:
        result["type"] = "unstructured"
        result["header_row"] = None

        text = "\n".join(
            str(value)
            for value in raw.iloc[:, 0].dropna().tolist()
        )

        result["text_preview"] = text[:2000]

        return result

    headers = [
        clean_column_name(value, i)
        for i, value in enumerate(raw.iloc[header_row])
    ]

    data = raw.iloc[header_row + 1:].copy()
    data.columns = headers
    data = data.dropna(how="all")

    data = convert_obvious_types(data)

    result["type"] = "tabular"
    result["header_row"] = int(header_row)
    result["data_rows"] = int(len(data))
    result["columns"] = [str(column) for column in data.columns]

    result["missing_values"] = {
        str(column): int(count)
        for column, count in data.isna().sum().items()
        if count > 0
    }

    result["total_missing_cells"] = int(data.isna().sum().sum())

    numeric_columns = data.select_dtypes(
        include="number"
    ).columns.tolist()

    result["numeric_columns"] = [str(column) for column in numeric_columns]

    result["numeric_summary"] = {}

    for column in numeric_columns:
        series = data[column].dropna()

        if len(series) == 0:
            continue

        result["numeric_summary"][str(column)] = {
            "count": int(series.count()),
            "sum": float(series.sum()),
            "mean": float(series.mean()),
            "minimum": float(series.min()),
            "maximum": float(series.max()),
        }

    identifier_columns = find_identifier_columns(data.columns)

    result["possible_duplicate_records"] = {}

    for column in identifier_columns:
        non_empty = data[column].dropna()

        duplicates = non_empty[
            non_empty.duplicated(keep=False)
        ]

        if not duplicates.empty:
            result["possible_duplicate_records"][str(column)] = {
                "duplicate_count": int(len(duplicates)),
                "duplicate_values": [
                    str(value)
                    for value in duplicates.unique()[:20]
                ],
            }

    result["sample_rows"] = (
        data.head(3)
        .astype(str)
        .replace("NaT", "")
        .replace("nan", "")
        .to_dict(orient="records")
    )

    return result


def analyze_workbook(path):
    xls = pd.ExcelFile(path)

    report = {
        "file": path.name,
        "sheet_count": len(xls.sheet_names),
        "sheets": [],
    }

    for sheet_name in xls.sheet_names:
        print(f"Analyzing: {sheet_name}")

        try:
            result = analyze_sheet(path, sheet_name)
            report["sheets"].append(result)
        except Exception as exc:
            report["sheets"].append({
                "sheet": sheet_name,
                "type": "error",
                "error": str(exc),
            })

    return report


def main():
    files = sorted(INCOMING_DIR.glob("*.xlsx"))

    if not files:
        print("No Excel workbook found.")
        return

    path = files[-1]

    print("=" * 80)
    print("WORKBOOK ANALYSIS")
    print("=" * 80)
    print("File:", path.name)

    report = analyze_workbook(path)

    output = INCOMING_DIR / f"{path.stem}_analysis.json"

    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("Report:", output)
    print("Sheets analyzed:", report["sheet_count"])

    for sheet in report["sheets"]:
        print(
            f"- {sheet['sheet']}: "
            f"{sheet.get('type', 'unknown')}"
        )


if __name__ == "__main__":
    main()
