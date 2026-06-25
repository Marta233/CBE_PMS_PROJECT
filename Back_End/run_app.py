"""
Start the PMS API and Celery worker in one terminal.

From Back_End/:
  python run_app.py              # uvicorn --reload + Celery worker
  python run_app.py --no-reload  # production-style (no file watcher)
  python run_app.py --no-worker  # API only (sync fallback if Redis down)

Replaces running uvicorn and run_worker in separate terminals.
"""
from __future__ import annotations

import argparse
import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BACK_END = Path(__file__).resolve().parent
SCRIPTS = BACK_END / "scripts"
WORKER_SCRIPT = SCRIPTS / "run_worker.py"

_child_procs: list[subprocess.Popen] = []


def _redis_up() -> bool:
    try:
        sys.path.insert(0, str(SCRIPTS))
        from cache.redis_client import redis_available

        return redis_available()
    except Exception:
        return False


def _start_process(name: str, cmd: list[str], *, cwd: Path) -> subprocess.Popen:
    print(f"  [{name}] {' '.join(cmd)}")
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
    )
    _child_procs.append(proc)
    return proc


def _shutdown_children() -> None:
    for proc in reversed(_child_procs):
        if proc.poll() is not None:
            continue
        print(f"\n  Stopping PID {proc.pid} ...")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


def _handle_exit(signum, frame) -> None:  # noqa: ARG001
    _shutdown_children()
    raise SystemExit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PMS API + Celery worker")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn reload")
    parser.add_argument("--no-worker", action="store_true", help="Skip Celery worker")
    args = parser.parse_args()

    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))

    print("=" * 60)
    print("  CBE PMS — starting API + worker")
    print("=" * 60)

    worker_proc: subprocess.Popen | None = None
    if not args.no_worker:
        if _redis_up():
            print("  Redis: OK")
            worker_proc = _start_process(
                "worker",
                [sys.executable, str(WORKER_SCRIPT)],
                cwd=BACK_END,
            )
            time.sleep(1.0)
            if worker_proc.poll() is not None:
                print("  WARNING: Celery worker exited immediately — check Redis and logs.")
                worker_proc = None
        else:
            print("  Redis: not reachable — worker skipped (API uses sync fallback)")
            print("  Start Redis, then re-run: python run_app.py")

    uvicorn_cmd = [
        sys.executable, "-m", "uvicorn", "api:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if not args.no_reload:
        uvicorn_cmd.append("--reload")

    signal.signal(signal.SIGINT, _handle_exit)
    signal.signal(signal.SIGTERM, _handle_exit)
    atexit.register(_shutdown_children)

    print(f"  API: http://127.0.0.1:{args.port}/docs")
    print("  Press Ctrl+C to stop API and worker")
    print("=" * 60)

    api_proc = _start_process("api", uvicorn_cmd, cwd=BACK_END)
    try:
        api_proc.wait()
    finally:
        _shutdown_children()

    if worker_proc and worker_proc.poll() not in (None, 0):
        sys.exit(worker_proc.returncode or 1)


if __name__ == "__main__":
    main()
