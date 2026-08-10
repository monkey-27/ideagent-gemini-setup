"""Run IDEAgent through OpenCode with one command.

    python scripts/run_ideagent_opencode.py

The wrapper reuses an existing OpenCode server when one is already listening. Otherwise
it opens the OpenCode TUI first so you can pick a model from `/models`, then starts
`opencode serve` on the port from the IDEAgent config, waits for it to come up, and runs
the normal IDEAgent entry point.
"""
from __future__ import annotations

import argparse
import shlex
import socket
import subprocess
import sys
import time
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


def _wait_for_server(
    host: str,
    port: int,
    *,
    timeout: float,
    process: subprocess.Popen | None,
    log_path: Path,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _server_ready(host, port):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"OpenCode exited before listening on {host}:{port}. See {log_path}."
            )
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for OpenCode on {host}:{port}. See {log_path}.")


def _opencode_command(command: str, port: int) -> list[str]:
    parts = shlex.split(command, posix=False)
    if not parts:
        raise ValueError("--opencode-command cannot be empty")
    if "--port" not in parts:
        parts.extend(["--port", str(port)])
    return parts


def _run_model_picker(command: str, port: int) -> int:
    cmd = _opencode_command(command, port)
    print()
    print("OpenCode is opening so you can pick the model from its picker.")
    print("Use /models or the model dropdown, select the model, then quit OpenCode to continue.")
    print()
    try:
        return subprocess.call(cmd, cwd=ROOT_DIR)
    except FileNotFoundError:
        print("Could not find `opencode` on PATH. Install OpenCode or pass --opencode-tui-command.", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IDEAgent through a local OpenCode server.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--opencode-tui-command",
        default="opencode",
        help="Interactive OpenCode command used for model selection.",
    )
    parser.add_argument(
        "--opencode-command",
        default="opencode serve",
        help="Command used when OpenCode is not already running.",
    )
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--no-start", action="store_true", help="Require OpenCode to already be running.")
    parser.add_argument("--keep-server", action="store_true", help="Do not stop OpenCode after IDEAgent exits.")
    parser.add_argument(
        "--skip-model-picker",
        action="store_true",
        help="Skip the OpenCode TUI and use OpenCode's already-saved/default model.",
    )
    args, extra = parser.parse_known_args()

    config_path = args.config if args.config.is_absolute() else ROOT_DIR / args.config
    base_url = _load_base_url(config_path)
    host, port = _host_port(base_url)

    process: subprocess.Popen | None = None
    log_path = ROOT_DIR / "opencode-server.log"
    log_file = None
    server_was_ready = _server_ready(host, port)

    if server_was_ready:
        print(f"Using existing OpenCode server at {base_url}.")
    elif args.no_start:
        print(f"OpenCode is not listening at {base_url}.", file=sys.stderr)
        return 1
    else:
        if not args.skip_model_picker:
            rc = _run_model_picker(args.opencode_tui_command, port)
            if rc not in (0, 130):
                return rc
        cmd = _opencode_command(args.opencode_command, port)
        print(f"Starting OpenCode: {' '.join(cmd)}")
        try:
            log_file = log_path.open("a", encoding="utf-8")
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            process = subprocess.Popen(
                cmd,
                cwd=ROOT_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            print("Could not find `opencode` on PATH. Install OpenCode or pass --opencode-command.", file=sys.stderr)
            return 1
        try:
            _wait_for_server(
                host,
                port,
                timeout=float(args.startup_timeout),
                process=process,
                log_path=log_path,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            if process is not None and process.poll() is None:
                process.terminate()
            return 1

    runner = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_ideagent.py"),
        "--config",
        str(config_path),
        *extra,
    ]
    try:
        return subprocess.call(runner, cwd=ROOT_DIR)
    finally:
        if process is not None and not args.keep_server and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if log_file is not None:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
