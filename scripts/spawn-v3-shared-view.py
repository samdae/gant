"""Launch one credential-isolated viewer. No scheduler module is imported."""
import os
import runpy
import subprocess
import sys
from pathlib import Path


def spawn(role, runtime):
    port = {"core": 8024, "edge": 8025}[role]
    project = Path(__file__).resolve().parents[1]
    env = runpy.run_path(str(project / "scripts/spawn-forecast-lab-public.py"))["public_environment"]()
    if role == "core":
        config = runtime / "shared-read/logins.json"
        if not config.is_file():
            raise RuntimeError("Shared reader configuration missing")
        env["GANT_SHARED_READ_CONFIG"] = str(config)
    logs = runtime / "logs"
    logs.mkdir(exist_ok=True)
    with (logs / f"shared-{role}.out.log").open("ab") as out, (logs / f"shared-{role}.err.log").open("ab") as err:
        subprocess.Popen([sys.executable, "-I", "-X", "utf8", "-m", "uvicorn",
            f"tradingagents.forecast_lab.shared_view:build_shared_{role}", "--factory",
            "--host", "127.0.0.1", "--port", str(port), "--no-access-log", "--no-proxy-headers",
            "--app-dir", str(project / "packages")], cwd=runtime, env=env,
            stdin=subprocess.DEVNULL, stdout=out, stderr=err, close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    spawn(sys.argv[1], Path(sys.argv[2]))
