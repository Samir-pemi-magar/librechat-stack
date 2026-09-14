from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INCOMING_DIR = BASE_DIR / "incoming"
REPORT_DIR = BASE_DIR / "reports"

KEEP_REPORTS = 4


def remove_files(directory: Path, patterns: list[str]) -> int:
    removed = 0

    if not directory.exists():
        return removed

    for pattern in patterns:
        for path in directory.glob(pattern):
            if path.is_file():
                path.unlink()
                removed += 1

    return removed


def cleanup_incoming() -> int:
    return remove_files(
        INCOMING_DIR,
        ["*.xlsx", "*.xls", "*.csv", "*.pdf"],
    )


def cleanup_generated_files() -> int:
    removed = 0

    removed += remove_files(
        REPORT_DIR,
        ["*.txt", "*.json", "*.png", "*.jpg", "*.jpeg"],
    )

    pdfs = sorted(
        REPORT_DIR.glob("*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for pdf in pdfs[KEEP_REPORTS:]:
        if pdf.is_file():
            pdf.unlink()
            removed += 1

    return removed


def cleanup() -> None:
    incoming_removed = cleanup_incoming()
    generated_removed = cleanup_generated_files()

    print("===== PIPELINE CLEANUP =====")
    print("Incoming files removed:", incoming_removed)
    print("Generated temporary files removed:", generated_removed)
    print("Recent PDF reports kept:", KEEP_REPORTS)


if __name__ == "__main__":
    cleanup()
