"""Open the OpenCode TUI and run IDEAgent visibly inside it.

    python scripts/run_ideagent_in_opencode.py

This starts or attaches to an OpenCode TUI server, then submits a TUI bash prompt that
runs IDEAgent with live role-progress lines enabled.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("configs/ideagent_opencode_smoke.yaml")
DEFAULT_BASE_URL = "http://localhost:4096"


def _load_base_url(config_path: Path) -> str:
    try:
        import yaml
    except ModuleNotFoundError:
        return DEFAULT_BASE_URL
    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except OSError:
        return DEFAULT_BASE_URL
    client = cfg.get("client") or {}
    return str(client.get("base_url") or DEFAULT_BASE_URL)


def _host_port(base_url: str) -> tuple[str, int]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    if parsed.port is not None:
        return host, int(parsed.port)
    return host, 443 if parsed.scheme == "https" else 80


def _server_ready(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    password = os.environ.get("OPENCODE_SERVER_PASSWORD")
    if password:
        username = os.environ.get("OPENCODE_SERVER_USERNAME", "opencode")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    return headers


def _post(base_url: str, path: str, payload: dict | None = None, timeout: float = 10.0) -> bool:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers=_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenCode returned HTTP {exc.code} for {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach OpenCode TUI server at {base_url}") from exc
    if not raw.strip():
        return True
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return True
    return bool(parsed)


def _wait_for_server(
    host: str,
    port: int,
    *,
    timeout: float,
    process: subprocess.Popen | None,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _server_ready(host, port):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError("OpenCode exited before its TUI server was reachable.")
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for OpenCode at {host}:{port}.")


def _split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=(os.name != "nt"))
    if not parts:
        raise ValueError("OpenCode command cannot be empty")
    return parts


def _tui_command(command: str, *, port: int, model: str | None, agent: str | None) -> list[str]:
    parts = _split_command(command)
    if "--port" not in parts:
        parts.extend(["--port", str(port)])
    if model and "--model" not in parts and "-m" not in parts:
        parts.extend(["--model", model])
    if agent and "--agent" not in parts:
        parts.extend(["--agent", agent])
    return parts


def _attach_command(command: str, *, base_url: str) -> list[str]:
    parts = _split_command(command)
    if len(parts) >= 2 and parts[:2] == ["opencode", "attach"]:
        if base_url not in parts:
            parts.append(base_url)
    if "--dir" not in parts:
        parts.extend(["--dir", str(ROOT_DIR)])
    return parts


def _quote_for_shell(value: str) -> str:
    return shlex.quote(value) if os.name != "nt" else value


def _ideagent_prompt(config: Path, python_cmd: str) -> str:
    rel_config = config
    try:
        rel_config = config.relative_to(ROOT_DIR)
    except ValueError:
        pass
    if os.name == "nt":
        command = (
            f'cmd /c "set IDEAGENT_LIVE_PROGRESS=1&& set PYTHONUNBUFFERED=1&& '
            f'{python_cmd} -u scripts\\run_ideagent.py --config {rel_config}"'
        )
    else:
        command = (
            "IDEAGENT_LIVE_PROGRESS=1 PYTHONUNBUFFERED=1 "
            f"{_quote_for_shell(python_cmd)} -u scripts/run_ideagent.py "
            f"--config {_quote_for_shell(str(rel_config))}"
        )
    return "!" + command


def _start_visible_tui(args: argparse.Namespace, base_url: str, host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["IDEAGENT_LIVE_PROGRESS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    if _server_ready(host, port):
        cmd = _attach_command(args.opencode_attach_command, base_url=base_url)
        print(f"Attaching OpenCode TUI: {' '.join(cmd)}")
    else:
        cmd = _tui_command(
            args.opencode_command,
            port=port,
            model=args.model,
            agent=args.agent,
        )
        print(f"Starting OpenCode TUI: {' '.join(cmd)}")
    try:
        return subprocess.Popen(cmd, cwd=ROOT_DIR, env=env)
    except FileNotFoundError:
        raise FileNotFoundError("Could not find `opencode` on PATH.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IDEAgent visibly inside OpenCode.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", help="Optional OpenCode model, in provider/model format.")
    parser.add_argument("--agent", help="Optional OpenCode primary agent to start with.")
    parser.add_argument("--python", default=sys.executable or "python")
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--submit-delay", type=float, default=1.0)
    parser.add_argument(
        "--open-models",
        action="store_true",
        help="Open OpenCode's model selector before submitting; combine with --submit-delay.",
    )
    parser.add_argument("--opencode-command", default="opencode")
    parser.add_argument("--opencode-attach-command", default="opencode attach")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without starting OpenCode.")
    args = parser.parse_args()

    config_path = args.config if args.config.is_absolute() else ROOT_DIR / args.config
    base_url = _load_base_url(config_path)
    host, port = _host_port(base_url)
    prompt = _ideagent_prompt(config_path, args.python)
    if args.dry_run:
        print(prompt)
        return 0

    try:
        process = _start_visible_tui(args, base_url, host, port)
        _wait_for_server(host, port, timeout=float(args.startup_timeout), process=process)
        if args.open_models:
            _post(base_url, "/tui/open-models")
        time.sleep(max(0.0, float(args.submit_delay)))
        _post(base_url, "/tui/clear-prompt")
        _post(base_url, "/tui/append-prompt", {"text": prompt})
        _post(base_url, "/tui/submit-prompt")
        _post(
            base_url,
            "/tui/show-toast",
            {"message": "IDEAgent run submitted. Watch the shell output for role progress."},
        )
        return process.wait()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
