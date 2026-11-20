"""Start both native services on loopback and stop both on Ctrl+C."""

import os
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from time import monotonic, sleep

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from app.config import Settings  # noqa: E402


def main():
    settings = Settings.from_env()
    if settings.api_host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("The local launcher requires a loopback API_HOST.")
    host = "127.0.0.1"
    api_url = f"http://{host}:{settings.api_port}"
    next_bin = ROOT / "node_modules/next/dist/bin/next"
    node = shutil.which("node")
    if not node or not next_bin.exists():
        raise SystemExit("Install Node.js and run npm ci first.")
    processes = []
    try:
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--app-dir",
                "services/api",
                "--host",
                host,
                "--port",
                str(settings.api_port),
            ],
            cwd=ROOT,
        )
        processes.append(api)
        deadline = monotonic() + 120
        with httpx.Client(trust_env=False, timeout=2) as client:
            while monotonic() < deadline:
                if api.poll() is not None:
                    raise SystemExit(f"The API exited with code {api.returncode}.")
                with suppress(httpx.RequestError):
                    if client.get(api_url + "/api/v1/ready").is_success:
                        break
                sleep(0.4)
            else:
                raise SystemExit("The API did not become ready within 120 seconds.")
        env = {**os.environ, "API_INTERNAL_URL": api_url, "NEXT_TELEMETRY_DISABLED": "1"}
        processes.append(
            subprocess.Popen(
                [node, str(next_bin), "dev", "--hostname", host, "--port", str(settings.web_port)],
                cwd=ROOT / "apps/web",
                env=env,
            )
        )
        print(f"Planner at http://{host}:{settings.web_port}", flush=True)
        while all(child.poll() is None for child in processes):
            sleep(0.5)
        raise SystemExit(
            next(child.returncode for child in processes if child.returncode is not None)
        )
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(processes):
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True
                    )
                else:
                    child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    main()
