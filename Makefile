.PHONY: help up down restart rebuild rebuild-all logs logs-all adapter scheduler weekly cleanup check config status

help:
	@echo ""
	@echo "Prarambha LibreChat Stack"
	@echo ""
	@echo "Docker:"
	@echo "  make up          Start the full Docker stack"
	@echo "  make down        Stop the full Docker stack"
	@echo "  make restart     Restart LibreChat"
	@echo "  make rebuild     Rebuild the custom LibreChat image"
	@echo "  make rebuild-all Rebuild all custom images"
	@echo "  make logs        Show LibreChat logs"
	@echo "  make logs-all    Show all Docker logs"
	@echo ""
	@echo "Python services:"
	@echo "  make adapter     Start the FastAPI code adapter"
	@echo "  make scheduler   Start the email/report scheduler"
	@echo "  make weekly      Run the weekly report immediately"
	@echo "  make cleanup     Clean processed pipeline files"
	@echo ""
	@echo "Checks:"
	@echo "  make check       Run production syntax checks"
	@echo "  make config      Validate Docker Compose"
	@echo "  make status      Show container status"
	@echo ""

up:
	./scripts/start-dev.sh

down:
	docker compose down

restart:
	docker compose restart librechat

rebuild:
	docker build --no-cache -t prarambha-librechat:custom -f librechat-custom/Dockerfile .

rebuild-all:
	docker build --no-cache -t prarambha-librechat:custom -f librechat-custom/Dockerfile .
	docker build --no-cache -t prarambha-code-sandbox:latest code-sandbox
	docker build --no-cache -t prarambha-local-scraper:latest local-scraper

logs:
	docker logs -f LibreChat

logs-all:
	docker compose logs -f

adapter:
	cd code-adapter && .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 9000

scheduler:
	cd code-adapter && .venv/bin/python integrated_scheduler.py

weekly:
	cd code-adapter && .venv/bin/python integrated_scheduler.py --run-weekly-now

cleanup:
	cd code-adapter && .venv/bin/python cleanup_pipeline.py

check:
	@echo "Checking Python syntax..."
	@cd code-adapter && .venv/bin/python -m py_compile \
		server.py \
		analyze_workbook.py \
		detect_anomalies.py \
		email_watcher.py \
		integrated_scheduler.py \
		weekly_report.py \
		pdf_report.py \
		smtp_sender.py \
		cleanup_pipeline.py
	@echo "Python syntax: OK"
	@echo ""
	@echo "Checking Docker Compose..."
	@docker compose config >/dev/null
	@echo "Docker Compose: OK"
	@echo ""
	@echo "All checks passed."

config:
	docker compose config >/dev/null && echo "Docker Compose configuration: OK"

status:
	docker compose ps
