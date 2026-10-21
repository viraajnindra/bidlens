"""Run API, durable worker, and website together; Ctrl+C stops all three."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.seed import seed


def main():
    if not shutil.which("pnpm") or not shutil.which("node"):
        raise SystemExit(
            "Install Node.js 22+ and pnpm 10.28.2, then run pnpm --dir frontend install."
        )
    seed()
    commands = [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT,
        ),
        ([sys.executable, "-m", "backend.worker"], ROOT),
        (["pnpm", "dev"], ROOT / "frontend"),
    ]
    processes = []
    try:
        for command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=os.environ.copy()))
        print(
            "\nBidLens: http://127.0.0.1:3000\nAPI docs: http://127.0.0.1:8000/docs\n", flush=True
        )
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
        if any(p.returncode not in (None, 0) for p in processes):
            raise SystemExit(
                "A service stopped. See its error above (ports 3000 and 8000 must be free)."
            )
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
