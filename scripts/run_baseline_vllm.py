"""Run IDEAgent baselines against a local vLLM OpenAI-compatible server.

    python scripts/run_baseline_vllm.py --mode stateless --model Qwen/Qwen2.5-7B-Instruct

The wrapper reuses an existing vLLM server on the requested port. Otherwise it starts
`vllm serve <model> --port <port>`, waits for `/v1/models`, writes a temporary config with
all baseline roles pointed at that same local model, and runs the selected baseline.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

MODES = {
    "stateless": (
        ROOT_DIR / "baselines" / "vllm" / "stateless.yaml",
        ROOT_DIR / "baselines" / "simple" / "run_simple_baseline.py",
    ),
    "single-shot": (
        ROOT_DIR / "baselines" / "vllm" / "single_shot.yaml",
        ROOT_DIR / "baselines" / "simple" / "run_simple_baseline.py",
    ),
    "sequential": (
        ROOT_DIR / "baselines" / "vllm" / "sequential_memory.yaml",
        ROOT_DIR / "baselines" / "simple" / "sequential_memory.py",
    ),
    "nova": (
        ROOT_DIR / "baselines" / "vllm" / "nova_closed_book.yaml",
        ROOT_DIR / "baselines" / "nova" / "run_nova_closed_book.py",
    ),
}


def _load_config(path: Path) -> dict:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required. Install dependencies first with `python -m pip install -e .`."
        ) from exc
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_config(config: dict, path: Path) -> None:
    import yaml

    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def _models_endpoint_ready(port: int, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{int(port)}/v1/models", timeout=timeout) as response:
            return 200 <= int(response.status) < 300
    except (OSError, urllib.error.URLError):
        return False


def _wait_for_server(
    port: int,
    *,
    timeout: float,
    process: subprocess.Popen | None,
    log_path: Path,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _models_endpoint_ready(port):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"vLLM exited before /v1/models was ready. See {log_path}.")
        time.sleep(1.0)
    raise TimeoutError(f"Timed out waiting for vLLM on localhost:{port}. See {log_path}.")


def _vllm_command(command: str, model: str, port: int) -> list[str]:
    parts = shlex.split(command, posix=(os.name != "nt"))
    if not parts:
        raise ValueError("--vllm-command cannot be empty")
    if "{model}" in parts:
        parts = [model if part == "{model}" else part for part in parts]
    elif len(parts) >= 2 and parts[:2] == ["vllm", "serve"]:
        parts.insert(2, model)
    if "--port" not in parts:
        parts.extend(["--port", str(port)])
    return parts


def _set_role(config: dict, section: str, *, model: str, port: int) -> None:
    role_cfg = dict(config.get(section) or {})
    role_cfg["model_id"] = model
    role_cfg["port"] = int(port)
    role_cfg["backend"] = "vllm"
    config[section] = role_cfg


def _runtime_config(config: dict, *, model: str, port: int, output_dir: str | None) -> dict:
    cfg = dict(config)
    client = dict(cfg.get("client") or {})
    client["backend"] = "vllm"
    client["api_key_env"] = client.get("api_key_env") or "VLLM_API_KEY"
    cfg["client"] = client
    for section in ("generator", "steno", "judge"):
        if section in cfg:
            _set_role(cfg, section, model=model, port=port)
    if output_dir:
        data = dict(cfg.get("data") or {})
        data["output_dir"] = output_dir
        cfg["data"] = data
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a baseline against local vLLM.")
    parser.add_argument(
        "--mode",
        choices=tuple(MODES),
        default="stateless",
        help="Baseline mode to run.",
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Model id served by vLLM and sent in OpenAI-compatible requests.",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional config template override.",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--startup-timeout", type=float, default=300.0)
    parser.add_argument("--no-start", action="store_true", help="Require vLLM to already be running.")
    parser.add_argument("--keep-server", action="store_true", help="Do not stop vLLM after the baseline exits.")
    parser.add_argument(
        "--vllm-command",
        default="vllm serve",
        help="Command used when vLLM is not already running. Use {model} as an explicit placeholder.",
    )
    args, extra = parser.parse_known_args()

    template_path, runner_path = MODES[args.mode]
    if args.config is not None:
        template_path = args.config if args.config.is_absolute() else ROOT_DIR / args.config
    try:
        config = _load_config(template_path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    process: subprocess.Popen | None = None
    log_path = ROOT_DIR / "vllm-server.log"
    log_file = None
    if _models_endpoint_ready(args.port):
        print(f"Using existing vLLM server at http://localhost:{args.port}/v1.")
    elif args.no_start:
        print(f"vLLM is not listening at http://localhost:{args.port}/v1.", file=sys.stderr)
        return 1
    else:
        cmd = _vllm_command(args.vllm_command, args.model, args.port)
        print(f"Starting vLLM: {' '.join(cmd)}")
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
            print("Could not find `vllm` on PATH. Install vLLM or start the server yourself.", file=sys.stderr)
            return 1
        try:
            _wait_for_server(
                args.port,
                timeout=float(args.startup_timeout),
                process=process,
                log_path=log_path,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            if process is not None and process.poll() is None:
                process.terminate()
            return 1

    print(f"Running {args.mode} baseline with vLLM model: {args.model}")
    runtime_config = _runtime_config(
        config, model=args.model, port=args.port, output_dir=args.output_dir
    )
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", prefix=f"ideagent-vllm-{args.mode}-",
            delete=False, encoding="utf-8"
        ) as f:
            tmp_path = Path(f.name)
        _write_config(runtime_config, tmp_path)
        command = [sys.executable, str(runner_path), "--config", str(tmp_path), *extra]
        return subprocess.call(command, cwd=ROOT_DIR)
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
