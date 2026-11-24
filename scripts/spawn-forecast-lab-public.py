"""Start the loopback public viewer from an isolated child environment on Windows."""

import os
import subprocess
import sys
from pathlib import Path


def public_environment():
    system_root = os.environ["SystemRoot"]
    return {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "PATH": str(Path(system_root) / "System32"),
        **{name: os.environ[name] for name in ("TEMP", "TMP") if name in os.environ},
    }


def launch(command, working_dir, log_dir):
    with (
        (log_dir / "public.out.log").open("ab") as out,
        (log_dir / "public.err.log").open("ab") as err,
    ):
        return subprocess.Popen(
            command, cwd=working_dir, env=public_environment(),
            stdin=subprocess.DEVNULL, stdout=out, stderr=err,
            close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )


if __name__ == "__main__":
    project = Path(__file__).resolve().parents[1]
    runtime = Path(sys.argv[1])
    public_dir = runtime / "public"
    public_dir.mkdir(exist_ok=True)
    launch(
        [
            sys.executable, "-I", "-X", "utf8", "-m", "uvicorn",
            "tradingagents.forecast_lab.public_app:app", "--host", "127.0.0.1",
            "--port", "8015", "--no-access-log", "--no-proxy-headers",
            "--app-dir", str(project / "packages"),
        ],
        public_dir, runtime / "logs",
    )
