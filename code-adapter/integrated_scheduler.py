import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler


BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

EMAIL_WATCHER = BASE_DIR / "email_watcher.py"
WEEKLY_REPORT = BASE_DIR / "weekly_report.py"
PDF_REPORT = BASE_DIR / "pdf_report.py"
SMTP_SENDER = BASE_DIR / "smtp_sender.py"
CLEANUP_PIPELINE = BASE_DIR / "cleanup_pipeline.py"


def run_script(script, *args):
    print(f"\n===== RUNNING: {script.name} =====", flush=True)

    result = subprocess.run(
        [PYTHON, str(script), *args],
        cwd=str(BASE_DIR),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{script.name} failed with exit code {result.returncode}"
        )

    print(f"===== COMPLETED: {script.name} =====", flush=True)


def email_check_job():
    print(
        f"\n===== EMAIL CHECK: {datetime.now().isoformat()} =====",
        flush=True,
    )

    try:
        run_script(EMAIL_WATCHER)
    except Exception as exc:
        print(f"EMAIL CHECK ERROR: {exc}", flush=True)


def weekly_report_job():
    print(
        f"\n===== WEEKLY REPORT: {datetime.now().isoformat()} =====",
        flush=True,
    )

    try:
        run_script(WEEKLY_REPORT)
        run_script(PDF_REPORT)

        workbooks = list((BASE_DIR / "incoming").glob("*.xlsx"))
        if not workbooks:
            raise FileNotFoundError("No Excel workbook found.")

        workbook = max(
            workbooks,
            key=lambda path: path.stat().st_mtime,
        )

        pdf_path = (
            BASE_DIR
            / "reports"
            / f"{workbook.stem}_weekly_report.pdf"
        )

        run_script(SMTP_SENDER, str(pdf_path), "sales")

        # Cleanup only after the report has been successfully sent.
        run_script(CLEANUP_PIPELINE)

        print(
            "\n===== WEEKLY REPORT COMPLETE =====",
            flush=True,
        )

    except Exception as exc:
        print(
            f"WEEKLY REPORT ERROR: {exc}",
            flush=True,
        )


def main():
    scheduler = BlockingScheduler(timezone=ZoneInfo("Asia/Kathmandu"))

    # Check Gmail every 5 minutes.
    scheduler.add_job(
        email_check_job,
        "interval",
        minutes=5,
        id="email_check",
        replace_existing=True,
        max_instances=1,
    )

    # Generate and send the report every Sunday at 09:00 Nepal time.
    scheduler.add_job(
        weekly_report_job,
        "cron",
        day_of_week="sun",
        hour=9,
        minute=0,
        id="weekly_report",
        replace_existing=True,
        max_instances=1,
    )

    if "--run-weekly-now" in sys.argv:
        print(
            "Manual weekly report test requested.",
            flush=True,
        )
        weekly_report_job()
        return

    print("========================================", flush=True)
    print("Integrated scheduler started.", flush=True)
    print("Gmail check: every 5 minutes", flush=True)
    print("Weekly report: Sunday at 09:00", flush=True)
    print("========================================", flush=True)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Integrated scheduler stopped.", flush=True)


if __name__ == "__main__":
    main()
