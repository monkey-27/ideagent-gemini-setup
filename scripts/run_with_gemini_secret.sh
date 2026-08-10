#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_FILE="${IDEAGENT_GEMINI_SECRET_FILE:-$ROOT_DIR/.env.gemini.secret}"
CONFIG_PATH="${IDEAGENT_CONFIG:-configs/ideagent_gemini_smoke.yaml}"

if [[ "${1:-}" == "--set-key" || "${1:-}" == "--replace-key" ]]; then
  exec "$ROOT_DIR/scripts/set_gemini_secret.sh"
fi

if [[ $# -gt 0 ]]; then
  CONFIG_PATH="$1"
  shift
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  if [[ ! -f "$SECRET_FILE" ]]; then
    echo "No GEMINI_API_KEY is exported and $SECRET_FILE does not exist." >&2
    echo "First run: ./scripts/set_gemini_secret.sh" >&2
    exit 1
  fi

  ENCODED_KEY="$(sed -n 's/^GEMINI_API_KEY_B64=//p' "$SECRET_FILE" | tail -n 1)"
  if [[ -z "$ENCODED_KEY" ]]; then
    echo "Secret file exists but has no GEMINI_API_KEY_B64 entry: $SECRET_FILE" >&2
    exit 1
  fi

  if DECODED_KEY="$(printf "%s" "$ENCODED_KEY" | base64 --decode 2>/dev/null)"; then
    :
  elif DECODED_KEY="$(printf "%s" "$ENCODED_KEY" | base64 -D 2>/dev/null)"; then
    :
  else
    echo "Could not decode GEMINI_API_KEY_B64 from $SECRET_FILE" >&2
    exit 1
  fi

  export GEMINI_API_KEY="$DECODED_KEY"
  unset ENCODED_KEY DECODED_KEY
  echo "Using stored Gemini key from $SECRET_FILE" >&2
  echo "To replace it, run: ./scripts/run_with_gemini_secret.sh --set-key" >&2
else
  echo "Using GEMINI_API_KEY from the current environment." >&2
fi

PYTHON_BIN="${IDEAGENT_PYTHON:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment not found at $PYTHON_BIN" >&2
  echo "From $ROOT_DIR, run: python3 -m venv .venv && .venv/bin/python -m pip install -e ." >&2
  exit 1
fi

cd "$ROOT_DIR"
exec "$PYTHON_BIN" scripts/run_ideagent.py --config "$CONFIG_PATH" "$@"
