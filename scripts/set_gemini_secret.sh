#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_FILE="$ROOT_DIR/.env.gemini.secret"

printf "Paste Gemini API key (input hidden): " >&2
IFS= read -r -s GEMINI_API_KEY_INPUT
printf "\n" >&2

GEMINI_API_KEY_INPUT="${GEMINI_API_KEY_INPUT//$'\r'/}"
if [[ -z "$GEMINI_API_KEY_INPUT" ]]; then
  echo "No key entered; nothing was stored." >&2
  exit 1
fi

umask 077
TMP_FILE="$(mktemp "$ROOT_DIR/.env.gemini.secret.XXXXXX")"
{
  echo "# Local IDEAgent Gemini secret."
  echo "# Base64 keeps the key out of casual plaintext views; it is not encryption."
  printf "GEMINI_API_KEY_B64="
  printf "%s" "$GEMINI_API_KEY_INPUT" | base64 | tr -d '\n'
  printf "\n"
} > "$TMP_FILE"
chmod 600 "$TMP_FILE"
mv "$TMP_FILE" "$SECRET_FILE"

unset GEMINI_API_KEY_INPUT
echo "Stored Gemini key in $SECRET_FILE"
echo "Run: ./scripts/run_with_gemini_secret.sh"
