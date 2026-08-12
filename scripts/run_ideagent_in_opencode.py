"""Open the OpenCode TUI and run IDEAgent visibly inside it.

    python scripts/run_ideagent_in_opencode.py

This starts OpenCode with an initial task prompt. OpenCode then runs IDEAgent through
its own bash tool, so progress appears as a normal OpenCode task instead of terminal
output being injected into the TUI from a parent process.
"""
from __future__ import annotations

import argparse
import os
import shlex
import socket
import subprocess
import sys
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


def _split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=(os.name != "nt"))
    if not parts:
        raise ValueError("OpenCode command cannot be empty")
    return parts


def _tui_command(
    command: str,
    *,
    port: int,
    model: str | None,
    agent: str | None,
    prompt: str,
    auto: bool,
) -> list[str]:
    parts = _split_command(command)
    if "--port" not in parts:
        parts.extend(["--port", str(port)])
    if model and "--model" not in parts and "-m" not in parts:
        parts.extend(["--model", model])
    if agent and "--agent" not in parts:
        parts.extend(["--agent", agent])
    if auto and "--auto" not in parts:
        parts.append("--auto")
    if "--prompt" not in parts:
        parts.extend(["--prompt", prompt])
    return parts


def _quote_for_shell(value: str) -> str:
    return shlex.quote(value) if os.name != "nt" else value


def _ideagent_shell_command(config: Path, python_cmd: str) -> str:
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
    return command


def _opencode_task_prompt(shell_command: str) -> str:
    return (
        "Run IDEAgent in this repository with your bash/shell tool. "
        "Show the command output in the OpenCode session and do not edit files. "
        "Use this exact command:\n\n"
        f"{shell_command}"
    )


def _start_visible_tui(args: argparse.Namespace, host: str, port: int, prompt: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["IDEAGENT_LIVE_PROGRESS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    if _server_ready(host, port):
        raise RuntimeError(
            f"OpenCode is already listening on {host}:{port}. "
            "Close that session first, or pass a different config/base_url port."
        )
    else:
        cmd = _tui_command(
            args.opencode_command,
            port=port,
            model=args.model,
            agent=args.agent,
            prompt=prompt,
            auto=not args.no_auto,
        )
        print("Starting OpenCode with an IDEAgent task prompt...")
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
    parser.add_argument("--startup-timeout", type=float, default=45.0, help=argparse.SUPPRESS)
    parser.add_argument("--submit-delay", type=float, default=1.0, help=argparse.SUPPRESS)
    parser.add_argument("--no-auto", action="store_true", help="Do not pass --auto to OpenCode.")
    parser.add_argument(
        "--open-models",
        action="store_true",
        help="Deprecated. Use --model provider/model, or pick a default model in OpenCode before running this.",
    )
    parser.add_argument("--opencode-command", default="opencode")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without starting OpenCode.")
    args = parser.parse_args()

    config_path = args.config if args.config.is_absolute() else ROOT_DIR / args.config
    base_url = _load_base_url(config_path)
    host, port = _host_port(base_url)
    shell_command = _ideagent_shell_command(config_path, args.python)
    prompt = _opencode_task_prompt(shell_command)
    if args.dry_run:
        print(prompt)
        return 0
    if args.open_models:
        print("--open-models no longer injects into the TUI. Use --model provider/model, or set the default in OpenCode first.")

    try:
        process = _start_visible_tui(args, host, port, prompt)
        return process.wait()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
