# Prarambha LibreChat + Code Intelligence Stack

## 1. Overview

This project provides a LibreChat-based internal AI system designed to combine conversational AI, web search, code execution, internal company data, automated data analysis, reporting, and email delivery.

The system uses **Qwen 3.6** as the primary AI model and extends LibreChat with custom tools and infrastructure.

### Main capabilities

- LibreChat employee chat interface
- Qwen 3.6 integration
- Web search through SearXNG
- Local web scraping
- Python code execution
- Bash execution
- Docker-based code sandbox
- Internal company-data tools
- Excel workbook analysis
- CSV analysis
- PDF reading
- Graph generation
- Business-rule anomaly detection
- PDF report generation
- Gmail IMAP email ingestion
- SMTP report delivery
- Scheduled email collection
- Scheduled weekly analysis
- Automatic cleanup of temporary company data

The project is designed as a **server-deployable system**, rather than a system that needs to remain permanently running on a developer's personal computer.

---

# 2. High-Level Architecture

```text
                         EMPLOYEE
                            |
                            v
                     +-------------+
                     |  LibreChat |
                     +------+------+
                            |
                            v
                        Qwen 3.6
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
     Web Search       Internal Data     Workbook Analysis
          |                 |                 |
          v                 v                 v
       SearXNG        FastAPI Adapter    Python Analysis
          |                                   |
          v                                   v
    Local Scraper                       Anomaly Detection
```

---

# 3. Automated Company Reporting Architecture

The automated company-data pipeline is separate from normal employee chat usage.

```text
                         GMAIL
                           |
                          IMAP
                           |
                           v
                   +---------------+
                   | Email Watcher |
                   +-------+-------+
                           |
                     Every 5 Minutes
                           |
                           v
                   Allowed Sender?
                           |
                           v
                   Download Attachments
                           |
                           v
                       incoming/
                           |
                           |
                       Every Sunday
                           |
                           v
                  Workbook Analysis
                           |
                           v
                  Anomaly Detection
                           |
                           v
                     Qwen 3.6
                           |
                           v
                   Generate Report
                           |
                           v
                     PDF Report
                           |
                           v
                         SMTP
                           |
                           v
                 Configured Recipients
                           |
                           v
                        Cleanup
```

The important separation is:

- **Email watcher** collects incoming company data regularly.
- **APScheduler** controls when tasks execute.
- **Python analysis** performs deterministic calculations.
- **Qwen** converts structured findings into a readable report.
- **PDF generation** produces the final document.
- **SMTP** sends the report.
- **Cleanup** removes temporary files only after successful delivery.

---

# 4. Docker Architecture

The project uses Docker for the LibreChat application, MongoDB, SearXNG, local scraper, and code sandbox.

```text
+-------------------------------------------------------+
|                  Docker Compose Stack                 |
|                                                       |
|  +------------+     +-------------+                  |
|  | LibreChat  |     |   MongoDB   |                  |
|  |   :3080    |     |  persistent |                  |
|  +------------+     +-------------+                  |
|         |                                             |
|         |                                             |
|  +------------+     +----------------------+          |
|  |  SearXNG   |     |   Local Scraper     |          |
|  |   :8080    |     |       :8000         |          |
|  +------------+     +----------------------+          |
+-------------------------------------------------------+

                    |
                    | HTTP
                    v

              FastAPI Adapter
                  :9000
                    |
                    v
              Docker CLI
                    |
                    v
            Code Sandbox Container
```

The FastAPI adapter currently runs outside Docker Compose because it needs to communicate with the Docker daemon and create isolated sandbox containers.

---

# 5. Project Structure

```text
librechat-stack/
│
├── docker-compose.yml
├── docker-compose.override.yml
├── librechat.yaml
├── .env
├── .env.example
├── .gitignore
├── README.md
│
├── librechat-custom/
│   ├── Dockerfile
│   └── tools/
│       ├── InternalData.js
│       └── WorkbookAnalysis.js
│
├── code-adapter/
│   ├── server.py
│   ├── email_watcher.py
│   ├── integrated_scheduler.py
│   ├── analyze_workbook.py
│   ├── detect_anomalies.py
│   ├── weekly_report.py
│   ├── pdf_report.py
│   ├── smtp_sender.py
│   ├── cleanup_pipeline.py
│   ├── requirements.txt
│   │
│   ├── incoming/
│   ├── reports/
│   └── .venv/
│
├── code-sandbox/
│   ├── Dockerfile
│   └── requirements.txt
│
├── local-scraper/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
│
└── searxng/
    └── settings.yml
```

---

# 6. Main Components

## LibreChat

LibreChat provides the employee-facing chat interface.

It is responsible for:

- Conversations
- Agent interaction
- Tool selection
- File interaction
- Web search integration
- Code execution integration
- Qwen communication

---

## Qwen 3.6

Qwen 3.6 is the primary reasoning model.

It is used for:

- Understanding employee requests
- Choosing tools
- Interpreting tool results
- Combining information from multiple tools
- Producing human-readable answers
- Producing reports from structured analysis results

Qwen should not be considered the authoritative source for company numerical data.

The preferred architecture is:

```text
Company Data
     |
     v
Python / Deterministic Analysis
     |
     v
Structured Results
     |
     v
Qwen
     |
     v
Human-readable Report
```

---

# 7. Web Search

Web search is provided through:

```text
SearXNG
```

LibreChat communicates with SearXNG for search requests.

A local scraper provides the Firecrawl-compatible scraping layer.

Architecture:

```text
Qwen
 |
 v
LibreChat Web Search
 |
 v
SearXNG
 |
 v
Search Results
 |
 v
Local Scraper
 |
 v
Web Content
```

---

# 8. Code Execution

The system supports code execution through a FastAPI adapter and Docker sandbox.

```text
LibreChat
    |
    v
execute_code
    |
    v
FastAPI Adapter :9000
    |
    v
Docker Sandbox
    |
    v
Python / Bash
    |
    v
Result
```

The sandbox is designed to prevent executed code from directly affecting the host system.

---

# 9. Docker Sandbox Security

The sandbox uses several restrictions.

Current sandbox configuration includes:

- No network access
- Read-only filesystem
- Dropped Linux capabilities
- `no-new-privileges`
- CPU limits
- Memory limits
- Process limits
- Non-root execution
- Dedicated `/workspace`

The sandbox image is:

```text
prarambha-code-sandbox:latest
```

---

# 10. Sandbox Python Libraries

The sandbox currently supports libraries including:

```text
pandas
openpyxl
pypdf
python-docx
reportlab
matplotlib
```

These allow the model to perform tasks such as:

- Excel analysis
- CSV analysis
- PDF reading
- Word document creation
- PDF generation
- Chart generation

---

# 11. FastAPI Code Adapter

The FastAPI adapter runs on:

```text
http://localhost:9000
```

Health endpoint:

```text
GET /health
```

The adapter provides the bridge between LibreChat and local Python/Docker functionality.

Example architecture:

```text
LibreChat
    |
    v
Custom Tool
    |
    v
FastAPI Adapter
    |
    v
Python functionality
```

---

# 12. Internal Data Tool

LibreChat exposes the custom tool:

```text
internal_data
```

It communicates with:

```text
POST /tools/internal-data
```

The tool is intended to provide a controlled interface to internal company information.

The current implementation contains development/test data.

For production, it should be connected to the actual company data source.

The important design principle is:

```text
Qwen
  |
  v
internal_data
  |
  v
Approved Internal Data Source
```

The model should not invent internal company information.

---

# 13. Workbook Analysis Tool

LibreChat exposes:

```text
workbook_analysis
```

This tool communicates with:

```text
POST /tools/analyze-workbook
```

It allows Qwen to request analysis of the latest company Excel workbook.

The tool can:

- Identify workbook sheets
- Identify likely header rows
- Inspect columns
- Identify numeric columns
- Calculate numeric summaries
- Detect duplicate identifiers
- Detect suspicious negative values
- Detect extreme values
- Check financial relationships
- Check inventory relationships
- Check project budgets
- Detect high missing-data concentration

---

# 14. Deterministic Analysis

A major design principle is separating deterministic analysis from AI interpretation.

For example:

```text
Excel Workbook
      |
      v
Python
      |
      +--> Row counts
      +--> Column counts
      +--> Numeric summaries
      +--> Duplicate detection
      +--> Missing values
      +--> Business rules
      +--> Financial checks
      +--> Inventory checks
      +--> Budget checks
      |
      v
Structured Findings
      |
      v
Qwen
```

This prevents the model from having to manually calculate important company figures.

---

# 15. Anomaly Detection

The anomaly detector currently checks rules including:

### Duplicate identifiers

Detects duplicate values in identifier columns.

### Negative values

Checks numeric fields where negative values may be suspicious, such as:

- Quantity
- Amount
- Cost
- Salary
- Revenue
- Expense
- Price
- Profit
- Budget

A negative value is treated as a **detected condition**, not automatically as proof of an error.

### Extreme values

Checks unusually large values such as:

- Extremely high salaries
- Extremely high quantities

### Financial checks

Checks relationships such as:

```text
Gross Revenue
-
Operating Expenses
=
Calculated Net Profit
```

and:

```text
Calculated Net Profit
vs
Reported Profit
```

### Inventory reconciliation

Checks:

```text
Closing Stock =
Opening Stock
+ Received
- Sold
- Damaged
```

### Project budget checks

Checks whether:

```text
Actual Cost > Budget
```

### Missing-data concentration

Identifies sheets with a high percentage of missing cells.

---

# 16. Qwen Grounding

The weekly report system deliberately restricts the factual source available to Qwen.

The report-generation prompt instructs Qwen:

- Only report facts explicitly returned by the anomaly detector.
- Do not invent employee names.
- Do not invent project names.
- Do not invent SKUs.
- Do not invent dates.
- Do not invent causes.
- Do not invent impacts.
- Do not invent unsupported percentages.
- Do not invent missing columns.
- Do not invent examples.

General recommendations are allowed, but they must be clearly distinguished from detected findings.

This creates the following model:

```text
                    TOOL RESULT
                         |
                         v
                +----------------+
                | Grounded Qwen  |
                +----------------+
                         |
                         v
                  Human-readable
                     report
```

---

# 17. Email Ingestion

The email watcher uses Gmail IMAP.

Its job is to collect incoming company files.

Current workflow:

```text
Gmail
  |
  v
IMAP
  |
  v
Search today's emails
  |
  v
Allowed sender?
  |
  +---- NO ---> Ignore
  |
  YES
  |
  v
UNSEEN message?
  |
  +---- NO ---> Ignore
  |
  YES
  |
  v
Download supported attachments
  |
  v
incoming/
```

---

# 18. Allowed Senders

Email processing is restricted using:

```text
ALLOWED_SENDERS
```

This prevents arbitrary senders from injecting files into the company-analysis pipeline.

Example:

```text
ALLOWED_SENDERS=sender@example.com
```

Multiple senders can be configured as comma-separated values.

---

# 19. Duplicate Email Protection

The email watcher searches for:

```text
UNSEEN
```

messages.

After successfully downloading supported attachments, the email is marked as Seen.

Therefore the same email is not repeatedly processed during every five-minute polling cycle.

---

# 20. Incoming Company Files

Incoming attachments are stored temporarily under:

```text
code-adapter/incoming/
```

Supported attachment types currently include:

```text
.xlsx
.xls
.csv
.pdf
```

The workbook analyzer currently focuses on `.xlsx`.

Legacy `.xls` support may require conversion or additional processing.

---

# 21. APScheduler

APScheduler controls the automated jobs.

The current scheduler uses:

```text
Timezone: Asia/Kathmandu
```

The email watcher runs:

```text
Every 5 minutes
```

The weekly report runs:

```text
Every Sunday at 09:00
```

The intended production flow is therefore:

```text
Email Collection
    |
    | Every 5 minutes
    v
Incoming Data
    |
    |
    | Sunday
    v
Full Analysis
    |
    v
Report
```

---

# 22. Manual Weekly Test

The weekly process can be executed manually.

From:

```text
code-adapter/
```

run:

```bash
python integrated_scheduler.py --run-weekly-now
```

This is useful for testing without waiting until Sunday.

---

# 23. Weekly Report Pipeline

The weekly job performs the following operations:

```text
1. Find latest workbook
2. Analyze workbook
3. Detect anomalies
4. Send structured findings to Qwen
5. Generate report text
6. Generate PDF
7. Send PDF through SMTP
8. Cleanup temporary pipeline files
```

Cleanup happens only after successful SMTP delivery.

---

# 24. PDF Generation

The PDF report is generated using:

```text
ReportLab
```

Charts are generated using:

```text
Matplotlib
```

The report contains sections such as:

- Executive Summary
- Detected Findings
- Recommended Follow-up Checks
- Data visualizations

Reports are stored under:

```text
code-adapter/reports/
```

---

# 25. SMTP Delivery

Reports are delivered using Gmail SMTP.

Recipient groups are configured separately.

Available configuration includes:

```text
SALES_REPORT_RECIPIENTS
FINANCE_REPORT_RECIPIENTS
OPERATIONS_REPORT_RECIPIENTS
```

This allows different report types to be sent to different groups.

Example:

```text
sales report
     |
     v
sales recipients

finance report
     |
     v
finance recipients

operations report
     |
     v
operations recipients
```

---

# 26. Report Type Routing

The SMTP sender supports report types:

```text
sales
finance
operations
```

The report type determines which recipient environment variable is used.

This makes it possible to extend the system later with additional departments.

---

# 27. Storage Cleanup

The cleanup system prevents company files and generated temporary files from accumulating indefinitely.

The cleanup script is:

```text
code-adapter/cleanup_pipeline.py
```

After successful SMTP delivery, it removes temporary incoming company files:

```text
.xlsx
.xls
.csv
.pdf
```

It also removes temporary generated artifacts:

```text
.txt
.json
.png
.jpg
.jpeg
```

The newest four PDF reports are retained.

---

# 28. Cleanup Safety

Cleanup is deliberately performed only after successful report delivery.

```text
Analysis
   |
   v
Report Generation
   |
   v
PDF
   |
   v
SMTP
   |
   +---- FAILED ----> Keep files
   |
   SUCCESS
   |
   v
Cleanup
```

If analysis fails, report generation fails, or SMTP fails, cleanup does not run.

This preserves files for troubleshooting.

---

# 29. LibreChat Files vs Company Pipeline Files

There are two separate types of storage.

### Company pipeline

```text
code-adapter/incoming/
code-adapter/reports/
```

These are managed by the cleanup pipeline.

### LibreChat application data

LibreChat conversation files and application data are separate.

The company pipeline cleanup must not delete LibreChat user files.

---

# 30. MongoDB Persistence

MongoDB uses:

```text
./data-node:/data/db
```

This directory contains persistent LibreChat database data.

Normal container recreation does not remove this data.

Do not delete:

```text
data-node/
```

unless intentionally destroying the LibreChat database.

Avoid using:

```bash
docker compose down -v
```

when database persistence is required.

---

# 31. Docker Compose Services

Current Compose services are:

### LibreChat

```text
Image:
prarambha-librechat:custom

Port:
3080
```

### MongoDB

```text
Image:
mongo:latest
```

Persistent storage:

```text
./data-node:/data/db
```

### SearXNG

```text
Image:
searxng/searxng:latest

Port:
8080
```

### Local Scraper

```text
Image:
prarambha-local-scraper:latest
```

---

# 32. Docker Images

The project uses three custom images.

## LibreChat

```text
prarambha-librechat:custom
```

Build:

```bash
docker build --no-cache \
  -t prarambha-librechat:custom \
  -f librechat-custom/Dockerfile .
```

## Code Sandbox

```text
prarambha-code-sandbox:latest
```

Build:

```bash
docker build \
  -t prarambha-code-sandbox:latest \
  ./code-sandbox
```

## Local Scraper

```text
prarambha-local-scraper:latest
```

Build:

```bash
docker build \
  -t prarambha-local-scraper:latest \
  ./local-scraper
```

All three custom images are reproducible from the project source.

---

# 33. Starting Docker

From the project root:

```bash
docker compose up -d
```

Check services:

```bash
docker compose ps
```

Expected application containers include:

```text
LibreChat
chat-mongodb
searxng
prarambha-local-scraper
```

---

# 34. Starting the FastAPI Adapter

Go to:

```bash
cd code-adapter
```

Create the environment if necessary:

```bash
python3.12 -m venv .venv
```

Activate:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the adapter:

```bash
uvicorn server:app --host 0.0.0.0 --port 9000
```

Health check:

```bash
curl http://localhost:9000/health
```

Expected response:

```text
{"status":"ok"}
```

---

# 35. Starting the Scheduler

In another terminal:

```bash
cd code-adapter
source .venv/bin/activate
python integrated_scheduler.py
```

The scheduler will:

- Check email every five minutes.
- Run the weekly pipeline every Sunday at 09:00 Nepal time.

---

# 36. Environment Configuration

Production secrets should be stored in:

```text
.env
```

A safe template is provided as:

```text
.env.example
```

Required categories include:

```text
Gmail account
Gmail application password
Allowed senders
Sales recipients
Finance recipients
Operations recipients
```

Never commit `.env` to Git.

---

# 37. Environment Example

The configuration concept is:

```text
GMAIL_ADDRESS=your-gmail-address@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password

ALLOWED_SENDERS=allowed-sender@example.com

SALES_REPORT_RECIPIENTS=sales@example.com
FINANCE_REPORT_RECIPIENTS=finance@example.com
OPERATIONS_REPORT_RECIPIENTS=operations@example.com
```

Real production values must be supplied by the deployment administrator.

---

# 38. Git Safety

The `.gitignore` excludes sensitive and temporary files.

Important exclusions include:

```text
.env
.venv/
__pycache__/
code-adapter/incoming/
code-adapter/reports/
*.log
.vscode/
```

This prevents:

- Passwords
- API credentials
- Temporary company files
- Generated reports
- Python environments
- Local logs

from accidentally being committed.

---

# 39. Current Tested Capabilities

The development implementation has been tested for the following capabilities:

| Capability | Status |
|---|---|
| LibreChat | Working |
| Qwen 3.6 | Working |
| Web Search | Working |
| Python execution | Working |
| Bash execution | Working |
| Docker sandbox | Working |
| CSV analysis | Working |
| Excel analysis | Working |
| PDF reading | Working |
| PDF generation | Working |
| Graph generation | Working |
| Generated file downloads | Working |
| Internal data tool | Working |
| Workbook analysis tool | Working |
| Anomaly detection | Working |
| Multi-tool chaining | Working |
| Web + internal data chaining | Working |
| File → Code → Graph | Working |
| PDF → Code → Graph | Working |
| Gmail IMAP | Working |
| Email attachment ingestion | Working |
| Duplicate email protection | Working |
| APScheduler | Working |
| Qwen report generation | Working |
| SMTP delivery | Working |
| Recipient routing | Working |
| Post-success cleanup | Working |
| Docker image rebuilding | Working |

---

# 40. Example Multi-Tool Flow

Qwen can combine multiple tools.

Example conceptual request:

```text
Check internal company information,
then search the web,
then compare the results.
```

The resulting architecture is:

```text
User
 |
 v
Qwen
 |
 +------> internal_data
 |
 +------> Web Search
 |
 v
Compare Results
 |
 v
Answer
```

For company reporting, the same principle can be applied to:

```text
Internal Company Data
        +
External Web Information
        +
Python Analysis
        |
        v
      Qwen
        |
        v
     Report
```

---

# 41. Data Grounding Principle

The system should distinguish between:

### Deterministic facts

Produced by:

- Python
- Database queries
- Workbook analysis
- Business rules
- Internal APIs

and:

### AI-generated interpretation

Produced by Qwen.

The preferred architecture is:

```text
                 SOURCE DATA
                     |
          +----------+----------+
          |                     |
          v                     v
     Python Rules          Internal APIs
          |                     |
          +----------+----------+
                     |
                     v
              Structured Facts
                     |
                     v
                   Qwen
                     |
                     v
              Explanation
```

This reduces hallucination risk.

---

# 42. Production Considerations

The current system is a development-ready foundation, but several components should be reviewed against actual company requirements before production.

## Real company data

The current internal data implementation is test data.

It should be connected to the actual company data source.

## Business rules

Anomaly rules should be reviewed with the company.

Different departments may require different rules.

## Report types

The current SMTP routing supports sales, finance, and operations.

Additional report types can be added.

## Excel formats

The current workbook analyzer focuses on `.xlsx`.

If `.xls` files are required, explicit support should be added.

## File naming

If multiple emails contain attachments with identical filenames, a unique naming strategy should be implemented to avoid overwriting files.

## Qwen configuration

The Qwen server address and model should ideally be moved into environment configuration for production deployments.

## Schedule configuration

The current scheduler uses fixed testing/production values:

```text
Email: every 5 minutes
Weekly report: Sunday 09:00
Timezone: Asia/Kathmandu
```

These can later be made configurable.

---

# 43. Security Considerations

Before production deployment:

- Keep `.env` private.
- Do not expose the Docker daemon publicly.
- Restrict access to the FastAPI adapter.
- Keep the sandbox isolated.
- Validate allowed email senders.
- Validate incoming file types.
- Consider file size limits.
- Consider attachment filename sanitization.
- Review business rules.
- Review report recipients.
- Use secure Gmail authentication.
- Protect MongoDB storage.
- Restrict server access.
- Keep Docker images updated.
- Review dependencies regularly.

---

# 44. Failure Handling

The system should fail safely.

### Email failure

If Gmail cannot be reached:

```text
Email collection fails
        |
        v
No files processed
        |
        v
Next scheduled check retries
```

### Analysis failure

If workbook analysis fails:

```text
No report
No cleanup
Files retained
```

### Qwen failure

If Qwen fails:

```text
No completed report
Files retained
```

### PDF failure

If PDF generation fails:

```text
No SMTP delivery
Files retained
```

### SMTP failure

If email delivery fails:

```text
No cleanup
Generated files retained
```

This allows investigation instead of silently deleting evidence.

---

# 45. Deployment Checklist

Before production:

```text
[ ] Docker installed
[ ] Docker Compose available
[ ] Python 3.12 installed
[ ] Project copied to server

[ ] .env configured
[ ] Gmail configured
[ ] Allowed senders configured
[ ] Report recipients configured
[ ] Qwen endpoint configured

[ ] LibreChat image built
[ ] Sandbox image built
[ ] Local scraper image built

[ ] MongoDB persistence verified
[ ] Docker Compose started
[ ] FastAPI adapter started
[ ] /health returns OK

[ ] LibreChat accessible
[ ] Qwen responds
[ ] Web search works
[ ] Code execution works
[ ] Docker sandbox works

[ ] Internal data tool works
[ ] Workbook analysis works
[ ] Anomaly detection works

[ ] Gmail IMAP works
[ ] Attachment download works
[ ] Duplicate protection works

[ ] PDF generation works
[ ] SMTP delivery works
[ ] Recipient routing works
[ ] Cleanup works

[ ] Manual weekly pipeline tested
[ ] Scheduler tested
```

---

# 46. Deployment Order

Recommended startup order:

```text
1. MongoDB
2. SearXNG
3. Local Scraper
4. LibreChat
5. FastAPI Adapter
6. Scheduler
```

Docker Compose handles dependencies for the Compose services.

The FastAPI adapter and scheduler are started separately.

---

# 47. Quick Start

From the project root:

### Build images

```bash
docker build --no-cache \
  -t prarambha-librechat:custom \
  -f librechat-custom/Dockerfile .

docker build \
  -t prarambha-code-sandbox:latest \
  ./code-sandbox

docker build \
  -t prarambha-local-scraper:latest \
  ./local-scraper
```

### Start Docker

```bash
docker compose up -d
```

### Start adapter

```bash
cd code-adapter
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 9000
```

### Start scheduler

In another terminal:

```bash
cd ~/prarambha/librechat-stack/code-adapter
source .venv/bin/activate
python integrated_scheduler.py
```

---

# 48. Manual Pipeline Test

To test the complete weekly process immediately:

```bash
cd ~/prarambha/librechat-stack/code-adapter
source .venv/bin/activate
python integrated_scheduler.py --run-weekly-now
```

The expected flow is:

```text
Workbook
   |
   v
Analysis
   |
   v
Anomaly Detection
   |
   v
Qwen
   |
   v
PDF
   |
   v
SMTP
   |
   v
Cleanup
```

---

# 49. Troubleshooting

## Check Docker services

```bash
docker compose ps
```

## Check LibreChat

```bash
docker logs LibreChat --tail 100
```

## Check MongoDB

```bash
docker logs chat-mongodb --tail 100
```

## Check SearXNG

```bash
docker logs searxng --tail 100
```

## Check Local Scraper

```bash
docker logs prarambha-local-scraper --tail 100
```

## Check FastAPI

```bash
curl http://localhost:9000/health
```

## Run weekly pipeline manually

```bash
cd code-adapter
source .venv/bin/activate
python integrated_scheduler.py --run-weekly-now
```

---

# 50. Known Development Limitations

The following are known areas for future improvement:

1. The current internal data tool uses test data.
2. Workbook anomaly rules should be reviewed against real business requirements.
3. `.xls` ingestion is accepted but workbook analysis primarily targets `.xlsx`.
4. Attachment filename collisions should be handled for production.
5. Qwen endpoint configuration should be environment-driven.
6. Scheduler times can be made environment-configurable.
7. Report routing can be expanded for additional departments.
8. More detailed audit logging can be added.
9. Production authentication and authorization should be reviewed.
10. File-size and attachment validation should be strengthened.

---

# 51. Implementation Responsibility

The implementation covers the technical foundation for:

- LibreChat
- Qwen integration
- Agent tools
- Web search
- Local scraping
- Code execution
- Docker sandboxing
- Internal data access
- Excel analysis
- Anomaly detection
- Gmail ingestion
- APScheduler
- Qwen report generation
- PDF generation
- SMTP delivery
- Report recipient routing
- Storage cleanup
- Docker deployment

The production organization must provide and approve:

- Real company data sources
- Business rules
- Production email accounts
- Allowed senders
- Report recipients
- Production Qwen infrastructure
- Security requirements
- Data-retention requirements

---

# 52. Final Architecture

```text
                           EMPLOYEE
                              |
                              v
                       +-------------+
                       |  LibreChat  |
                       +------+------+
                              |
                              v
                          Qwen 3.6
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
         Web Search     Internal Data    Workbook Tool
             |                |                |
             v                v                v
          SearXNG        FastAPI Adapter  Python Analysis
             |                                 |
             v                                 v
       Local Scraper                     Anomaly Detection
             |                                 |
             +----------------+----------------+
                              |
                              v
                       Grounded Results


                    AUTOMATED REPORTING

                            Gmail
                              |
                             IMAP
                              |
                              v
                       Email Watcher
                              |
                        Every 5 Minutes
                              |
                              v
                       Allowed Sender
                              |
                              v
                         Attachments
                              |
                              v
                          incoming/
                              |
                         Every Sunday
                              |
                              v
                      Python Analysis
                              |
                              v
                     Anomaly Detection
                              |
                              v
                          Qwen 3.6
                              |
                              v
                       PDF Generator
                              |
                              v
                            SMTP
                              |
                              v
                    Report Recipients
                              |
                         SMTP SUCCESS
                              |
                              v
                           Cleanup
                              |
                    +---------+---------+
                    |                   |
                    v                   v
             Temporary files      Keep latest
                removed            4 PDFs
```

---

# 53. Handoff Summary

The system is intended to provide an internal AI platform where employees can use LibreChat and Qwen while the same infrastructure supports automated company-data processing.

The complete automated workflow is:

```text
Gmail
  ↓
IMAP
  ↓
Email Watcher
  ↓
Incoming Company Files
  ↓
Python Workbook Analysis
  ↓
Deterministic Anomaly Detection
  ↓
Qwen 3.6
  ↓
Grounded Report
  ↓
PDF Generation
  ↓
SMTP
  ↓
Department Recipients
  ↓
Cleanup
```

The architecture separates:

- **Data collection**
- **Deterministic analysis**
- **AI reasoning**
- **Report generation**
- **Email delivery**
- **Storage cleanup**

This separation makes the system easier to maintain, test, and deploy.

The current implementation has already been tested across the major components, including LibreChat, Qwen, web search, code execution, Docker sandboxing, workbook analysis, anomaly detection, Gmail ingestion, scheduling, PDF generation, SMTP delivery, and cleanup.

Before production deployment, the remaining work should focus primarily on replacing development/test data with real company data, confirming business rules, reviewing security requirements, and finalizing production configuration.