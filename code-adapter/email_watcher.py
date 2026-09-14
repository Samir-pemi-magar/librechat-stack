import os
import imaplib
import email
from email.header import decode_header
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"
INCOMING_DIR = BASE_DIR / "incoming"

ALLOWED_EXTENSIONS = {
    ".xlsx",
    ".xls",
    ".csv",
    ".pdf",
}


def load_env():
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env not found: {ENV_FILE}")

    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def decode_text(value):
    if not value:
        return ""

    result = []

    for text, encoding in decode_header(value):
        if isinstance(text, bytes):
            result.append(
                text.decode(
                    encoding or "utf-8",
                    errors="replace",
                )
            )
        else:
            result.append(text)

    return "".join(result)


def get_allowed_senders():
    return {
        sender.strip().lower()
        for sender in os.environ.get("ALLOWED_SENDERS", "").split(",")
        if sender.strip()
    }


def extract_email_address(value):
    value = decode_text(value)

    if "<" in value and ">" in value:
        return value.split("<", 1)[1].split(">", 1)[0].strip().lower()

    return value.strip().lower()


def save_attachments(message):
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = []

    for part in message.walk():
        filename = part.get_filename()

        if not filename:
            continue

        filename = decode_text(filename)
        extension = Path(filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            continue

        payload = part.get_payload(decode=True)

        if not payload:
            continue

        safe_name = Path(filename).name
        output_path = INCOMING_DIR / safe_name

        output_path.write_bytes(payload)

        downloaded.append(output_path)
        print(f"Downloaded: {output_path}")

    return downloaded


def check_email():
    load_env()

    allowed_senders = get_allowed_senders()

    if not allowed_senders:
        raise RuntimeError("ALLOWED_SENDERS is empty.")

    print("Connecting to Gmail...")

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)

    mail.login(
        os.environ["GMAIL_ADDRESS"],
        os.environ["GMAIL_APP_PASSWORD"],
    )

    try:
        status, _ = mail.select("INBOX")

        if status != "OK":
            raise RuntimeError("Could not select Gmail INBOX.")

        from datetime import datetime

        today = datetime.now().strftime("%d-%b-%Y")

        matching_ids = []

        for sender in allowed_senders:
            status, data = mail.search(
                None,
                f'(FROM "{sender}" SINCE "{today}" UNSEEN)',
            )

            if status != "OK":
                raise RuntimeError(f"Could not search Gmail for sender: {sender}")

            if data and data[0]:
                matching_ids.extend(data[0].split())

        # Remove duplicate message IDs and process only the newest 20.
        message_ids = sorted(
            set(matching_ids),
            key=lambda value: int(value),
            reverse=True,
        )[:20]

        print(f"Today's matching emails found: {len(message_ids)}")

        processed_emails = 0
        downloaded_files = 0

        for message_id in message_ids:
            status, msg_data = mail.fetch(
                message_id,
                "(BODY.PEEK[])",
            )

            if status != "OK":
                print(f"Could not fetch message {message_id!r}")
                continue

            raw_email = b"".join(
                part[1]
                for part in msg_data
                if isinstance(part, tuple)
            )

            message = email.message_from_bytes(raw_email)

            sender = extract_email_address(message.get("From"))

            if sender not in allowed_senders:
                continue

            subject = decode_text(message.get("Subject"))

            print()
            print("Allowed email found")
            print("From:", sender)
            print("Subject:", subject)

            attachments = save_attachments(message)

            if attachments:
                processed_emails += 1
                downloaded_files += len(attachments)

                # Mark this email as read only after successful processing.
                mail.store(message_id, "+FLAGS", "\\Seen")

            else:
                print("No supported attachments found.")

        print()
        print("===== EMAIL WATCHER RESULT =====")
        print("Allowed emails processed:", processed_emails)
        print("Attachments downloaded:", downloaded_files)

    finally:
        mail.logout()


if __name__ == "__main__":
    check_email()
