"""Run IDEAgent through local Ollama with one command.

    python scripts/run_ideagent_ollama.py --model llama3.2

The wrapper reuses an existing Ollama server when one is already listening. Otherwise it
starts `ollama serve`, waits for it, selects a model from --model, OLLAMA_MODEL, or the
first installed Ollama model, then runs the normal IDEAgent entry point.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("configs/ideagent_ollama_smoke.yaml")
DEFAULT_BASE_URL = "http://localhost:11434"
ROLES = ("ideator", "critic", "quality", "steno", "judge")


def _load_config(config_path: Path) -> dict:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required. Install dependencies first with `python -m pip install -e .`."
        ) from exc
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_config(config: dict, path: Path) -> None:
    import yaml

    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


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
            raise RuntimeError(f"Ollama exited before listening on {host}:{port}. See {log_path}.")
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for Ollama on {host}:{port}. See {log_path}.")


def _ollama_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=False)
    if not parts:
        raise ValueError("--ollama-command cannot be empty")
    return parts


def _get_json(base_url: str, path: str, timeout: float) -> dict:
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def _installed_models(base_url: str, timeout: float) -> list[str]:
    try:
        payload = _get_json(base_url, "/api/tags", timeout)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []
    models = []
    for item in payload.get("models") or []:
        if isinstance(item, dict) and item.get("name"):
            models.append(str(item["name"]))
    return models


def _select_model(args: argparse.Namespace, base_url: str) -> str | None:
    if args.model:
        return str(args.model)
    env_model = os.environ.get("OLLAMA_MODEL")
    if env_model:
        return env_model
    installed = _installed_models(base_url, timeout=10.0)
    return installed[0] if installed else None


def _set_all_role_models(config: dict, model: str) -> dict:
    cfg = dict(config)
    agents = dict(cfg.get("agents") or {})
    for role in ROLES:
        role_cfg = dict(agents.get(role) or {})
        role_cfg["model_id"] = model
        agents[role] = role_cfg
    cfg["agents"] = agents
    client = dict(cfg.get("client") or {})
    client["backend"] = "ollama"
    cfg["client"] = client
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IDEAgent through a local Ollama server.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", help="Ollama model to use, e.g. llama3.2 or qwen2.5-coder:32b.")
    parser.add_argument("--ollama-command", default="ollama serve")
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--no-start", action="store_true", help="Require Ollama to already be running.")
    parser.add_argument("--keep-server", action="store_true", help="Do not stop Ollama after IDEAgent exits.")
    args, extra = parser.parse_known_args()

    config_path = args.config if args.config.is_absolute() else ROOT_DIR / args.config
    try:
        config = _load_config(config_path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    client = config.get("client") or {}
    base_url = str(client.get("base_url") or DEFAULT_BASE_URL)
    host, port = _host_port(base_url)

    process: subprocess.Popen | None = None
    log_path = ROOT_DIR / "ollama-server.log"
    log_file = None
    if _server_ready(host, port):
        print(f"Using existing Ollama server at {base_url}.")
    elif args.no_start:
        print(f"Ollama is not listening at {base_url}.", file=sys.stderr)
        return 1
    else:
        cmd = _ollama_command(args.ollama_command)
        print(f"Starting Ollama: {' '.join(cmd)}")
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
            print("Could not find `ollama` on PATH. Install Ollama or pass --ollama-command.", file=sys.stderr)
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

    model = _select_model(args, base_url)
    if not model:
        print(
            "No Ollama model found. Pull one first, for example:\n"
            "  ollama pull llama3.2\n"
            "Then rerun:\n"
            "  python scripts/run_ideagent_ollama.py --model llama3.2",
            file=sys.stderr,
        )
        return 1
    print(f"Using Ollama model: {model}")

    runtime_config = _set_all_role_models(config, model)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", prefix="ideagent-ollama-", delete=False, encoding="utf-8"
        ) as f:
            tmp_path = Path(f.name)
        _write_config(runtime_config, tmp_path)
        runner = [
            sys.executable,
            str(ROOT_DIR / "scripts" / "run_ideagent.py"),
            "--config",
            str(tmp_path),
            *extra,
        ]
        return subprocess.call(runner, cwd=ROOT_DIR)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
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
