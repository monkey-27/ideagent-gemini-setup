#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-configs/ideagent_opencode.yaml}"
PORT="${OPENCODE_PORT:-4096}"
HOST="${OPENCODE_HOST:-127.0.0.1}"
LOG_PATH="${OPENCODE_SERVER_LOG:-opencode-server.log}"

choose_python() {
  if [ -x .venv/bin/python ]; then
    printf '%s\n' ".venv/bin/python"
  elif command -v python3.12 >/dev/null 2>&1; then
    printf '%s\n' "python3.12"
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
  else
    printf '%s\n' "python"
  fi
}

PY="$(choose_python)"

server_ready() {
  "$PY" - "$HOST" "$PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=1.0):
        pass
except OSError:
    raise SystemExit(1)
PY
}

if ! server_ready; then
  if ! command -v opencode >/dev/null 2>&1; then
    echo "[ideagent] ERROR: opencode is not on PATH." >&2
    exit 1
  fi

  echo "[ideagent] OpenCode server is not reachable at http://localhost:${PORT}; starting it."
  echo "[ideagent] Tip: to use the exact model selected in the OpenCode dropdown, open the TUI with: opencode --port ${PORT}"
  nohup opencode serve --port "$PORT" > "$LOG_PATH" 2>&1 &
  server_pid=$!
  echo "[ideagent] OpenCode server PID: ${server_pid}; log: ${LOG_PATH}"

  for _ in $(seq 1 40); do
    if server_ready; then
      break
    fi
    if ! kill -0 "$server_pid" 2>/dev/null; then
      echo "[ideagent] ERROR: opencode serve exited early. Last log lines:" >&2
      tail -50 "$LOG_PATH" >&2 || true
      exit 1
    fi
    sleep 0.5
  done

  if ! server_ready; then
    echo "[ideagent] ERROR: timed out waiting for opencode serve on port ${PORT}." >&2
    echo "[ideagent] Check ${LOG_PATH} for details." >&2
    exit 1
  fi
else
  echo "[ideagent] OpenCode server already reachable at http://localhost:${PORT}."
fi

echo "[ideagent] Running IDEAgent config: ${CONFIG}"
echo "[ideagent] Python: ${PY}"
IDEAGENT_LIVE_PROGRESS=1 PYTHONUNBUFFERED=1 "$PY" -u scripts/run_ideagent.py --config "$CONFIG"
