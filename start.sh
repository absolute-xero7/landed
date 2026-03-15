#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Generating demo documents..."
(cd "$ROOT_DIR/backend" && .venv/bin/python demo/generate_demo_docs.py)

echo "Starting Landed backend on :8000..."
(cd "$ROOT_DIR/backend" && .venv/bin/uvicorn main:app --reload --port 8000) &
BACKEND_PID=$!

echo "Starting Railtracks visualizer on :3030..."
echo "Using 'railtracks viz' for the installed CLI version."
(cd "$ROOT_DIR/backend" && .venv/bin/railtracks viz) &
VISUALIZER_PID=$!

echo "Starting Landed frontend on :3000..."
(cd "$ROOT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "  App:        http://localhost:3000"
echo "  API:        http://localhost:8000"
echo "  Visualizer: http://localhost:3030"
echo ""
echo "Demo: drag backend/demo/*.pdf files into the upload zone"

trap "kill $BACKEND_PID $VISUALIZER_PID $FRONTEND_PID" SIGINT SIGTERM EXIT
wait
