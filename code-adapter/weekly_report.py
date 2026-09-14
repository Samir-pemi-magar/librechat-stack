import json
import os
from pathlib import Path

import requests

from analyze_workbook import analyze_workbook
from detect_anomalies import detect_anomalies


BASE_DIR = Path(__file__).resolve().parent
INCOMING_DIR = BASE_DIR / "incoming"
REPORT_DIR = BASE_DIR / "reports"


# Qwen configuration
# Set QWEN_BASE_URL in your local .env file.
# Example:
# QWEN_BASE_URL=http://your-server:20010/v1
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "http://localhost:20010/v1",
).rstrip("/")

QWEN_URL = f"{QWEN_BASE_URL}/chat/completions"

QWEN_MODEL = os.getenv(
    "QWEN_MODEL",
    "palmfuture/Qwen3.6-35B-A3B-GPTQ-Int4",
)


def find_latest_workbook():
    files = sorted(INCOMING_DIR.glob("*.xlsx"))

    if not files:
        raise FileNotFoundError("No .xlsx workbook found in incoming/.")

    return files[-1]


def build_prompt(workbook_name, anomalies):
    return f"""
You are generating an internal company data-quality report.

IMPORTANT GROUNDING RULES:
- The ANOMALY DETECTION section below is the ONLY source of factual information.
- Report ONLY facts explicitly stated in that section.
- Do NOT inspect, infer, reconstruct, or guess information about the workbook.
- Do NOT invent employee names, project names, SKUs, dates, causes, impacts, percentages, missing columns, or examples.
- Do NOT add facts from your general knowledge.
- A negative value is a detected condition, not automatically proof of an error.
- Recommendations may be general follow-up actions, but clearly distinguish them from detected findings.
- If a requested detail is not present, say that it is not available.

Workbook:
{workbook_name}

ANOMALY DETECTION:
{json.dumps(anomalies, indent=2, default=str)}

Produce a concise report with exactly these sections:

1. Executive Summary
2. Detected Findings
3. Recommended Follow-up Checks

Every factual statement in sections 1 and 2 must be directly supported by the anomaly results above.
"""


def call_qwen(prompt):
    response = requests.post(
        QWEN_URL,
        headers={
            "Content-Type": "application/json",
        },
        json={
            "model": QWEN_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful internal data analyst. "
                        "Answer concisely and do not spend tokens on lengthy reasoning. "
                        "Only report facts supported by the supplied tool output."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.2,
            "max_tokens": 4000,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()
    choice = data["choices"][0]
    message = choice["message"]

    print("QWEN FINISH_REASON:", choice.get("finish_reason"))
    print("QWEN CONTENT_LENGTH:", len(message.get("content") or ""))
    print(
        "QWEN REASONING_LENGTH:",
        len(message.get("reasoning_content") or ""),
    )

    return message.get("content") or ""


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    workbook = find_latest_workbook()

    print(f"Analyzing workbook: {workbook.name}")

    analysis = analyze_workbook(workbook)
    anomalies = detect_anomalies(workbook, analysis)

    print(f"Anomalies detected: {len(anomalies)}")
    print("Sending analysis to Qwen...")

    prompt = build_prompt(
        workbook.name,
        anomalies,
    )

    report = call_qwen(prompt)

    output = REPORT_DIR / f"{workbook.stem}_weekly_report.txt"
    output.write_text(report, encoding="utf-8")

    print()
    print("===== WEEKLY REPORT =====")
    print(report)
    print()
    print(f"Report saved: {output}")


if __name__ == "__main__":
    main()