#!/usr/bin/env bash
set -Eeuo pipefail

LIBRECHAT_DIR="$HOME/librechat-stack"
ADAPTER_DIR="$LIBRECHAT_DIR/code-adapter"
ADAPTER_LOG="/tmp/librechat-code-adapter.log"
ADAPTER_PID="/tmp/librechat-code-adapter.pid"

echo "===================================="
echo " Starting your AI development stack"
echo "===================================="

echo
echo "[1/3] Starting LibreChat and supporting services..."
docker compose -f "$LIBRECHAT_DIR/docker-compose.yml" up -d

echo
echo "[2/3] Starting Qwen inference..."
docker compose -f "$LIBRECHAT_DIR/inference/compose.yaml" up -d

echo "Waiting for the Qwen API..."
for attempt in $(seq 1 60); do
    if curl --fail --silent http://localhost:8001/v1/models >/dev/null; then
        echo "Qwen API is ready."
        break
    fi

    if [ "$attempt" -eq 60 ]; then
        echo "ERROR: Qwen API did not become ready within 120 seconds."
        echo "Check: docker logs --tail 80 qwen-inference"
        exit 1
    fi

    sleep 2
done

echo
echo "[3/3] Starting the code adapter..."

if curl --fail --silent --max-time 2 http://localhost:9000/health >/dev/null; then
    echo "Code adapter is already healthy."
else
    if [ -f "$ADAPTER_PID" ] && kill -0 "$(cat "$ADAPTER_PID")" 2>/dev/null; then
        echo "An adapter process exists; waiting for its health endpoint..."
    else
        rm -f "$ADAPTER_PID"
        cd "$ADAPTER_DIR"
        nohup "$ADAPTER_DIR/.venv/bin/uvicorn" server:app \
            --host 0.0.0.0 --port 9000 \
            >> "$ADAPTER_LOG" 2>&1 < /dev/null &
        echo "$!" > "$ADAPTER_PID"
    fi

    for attempt in $(seq 1 15); do
        if curl --fail --silent --max-time 2 http://localhost:9000/health >/dev/null; then
            echo "Code adapter is ready."
            break
        fi

        if [ "$attempt" -eq 15 ]; then
            echo "ERROR: Code adapter did not become healthy."
            echo "Recent adapter logs:"
            tail -n 40 "$ADAPTER_LOG" || true
            exit 1
        fi

        sleep 2
    done
fi

echo
echo "===================================="
echo " Development services are started"
echo "===================================="
echo "LibreChat:    http://localhost:3080"
echo "Qwen API:     http://localhost:8001/v1"
echo "SearXNG:      http://localhost:8080"
echo "Code adapter: http://localhost:9000/health"
echo
echo "Container status:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
