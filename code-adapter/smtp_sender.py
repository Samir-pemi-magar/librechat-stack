import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"
REPORT_DIR = BASE_DIR / "reports"


def load_env():
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env not found: {ENV_FILE}")

    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def get_recipients(report_type):
    env_key = f"{report_type.upper()}_REPORT_RECIPIENTS"
    raw = os.environ.get(env_key, "")

    recipients = [
        address.strip()
        for address in raw.split(",")
        if address.strip()
    ]

    if not recipients:
        raise RuntimeError(
            f"{env_key} is empty in .env"
        )

    return recipients


def find_latest_pdf():
    files = sorted(
        REPORT_DIR.glob("*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            f"No PDF report found in {REPORT_DIR}"
        )

    return files[0]


def send_report(pdf_path=None, report_type="sales"):
    load_env()

    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipients = get_recipients(report_type)

    if pdf_path is None:
        pdf_path = find_latest_pdf()
    else:
        pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Report PDF not found: {pdf_path}"
        )

    message = EmailMessage()

    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = "Weekly Company Data Analysis Report"

    message.set_content(
        "Hello,\n\n"
        "Attached is the weekly company data analysis report.\n\n"
        "This report was generated automatically from the latest "
        "available company workbook.\n\n"
        "Regards,\n"
        "Automated Data Analysis System"
    )

    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )

    print("Connecting to Gmail SMTP...")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)

    print()
    print("===== SMTP RESULT =====")
    print("Email sent successfully.")
    print("Recipients:", len(recipients))
    print("Attachment:", pdf_path.name)


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    report_type = sys.argv[2] if len(sys.argv) > 2 else "sales"

    send_report(pdf_path, report_type)
