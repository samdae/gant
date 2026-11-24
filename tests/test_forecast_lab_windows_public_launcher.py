"""Exercise the Windows PowerShell 5.1 task command against a temporary public service."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "native Windows task launcher")
class PublicLauncherTest(unittest.TestCase):
    def test_start_idempotence_env_and_private_recovery(self):
        with tempfile.TemporaryDirectory(prefix="public launch ") as directory:
            project = Path(directory)
            scripts = project / "scripts"
            scripts.mkdir()
            package = project / "packages/tradingagents/forecast_lab"
            package.mkdir(parents=True)
            (package.parent / "__init__.py").touch()
            (package / "__init__.py").touch()
            (package / "public_app.py").write_text(
                """import json, os
async def app(scope, receive, send):
    if scope['type'] != 'http': return
    data = json.dumps(dict(service='forecast-lab-public',ok=True, pid=os.getpid(),
        leaked=any(key in os.environ for key in ('FORECAST_LAB_DSN','PRIVATE_ADMIN_TOKEN','PYTHONPATH')))).encode()
    await send(dict(type='http.response.start',status=200,headers=[(b'content-type',b'application/json')]))
    await send(dict(type='http.response.body',body=data))
""", encoding="utf8")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = str(sock.getsockname()[1])
            for name in ("start-forecast-lab-public.ps1", "spawn-forecast-lab-public.py"):
                src = (ROOT / "scripts" / name).read_text(encoding="utf-8-sig")
                src = src.replace("8015", port).replace(
                    "Join-Path $project '.venv/Scripts/python.exe'", "'" + sys.executable.replace("'", "''") + "'")
                (scripts / name).write_text(src, encoding="utf-8-sig")
            entry = scripts / "start-forecast-lab-services.ps1"
            shutil.copy(ROOT / "scripts" / entry.name, entry)
            (scripts / "start-forecast-lab.ps1").write_text(
                'param([string]$EnvFile)\nWrite-Output PRIVATE_LAUNCH_ATTEMPTED', encoding="utf8")
            env = dict(os.environ, LOCALAPPDATA=directory, FORECAST_LAB_DSN="test-only",
                       PRIVATE_ADMIN_TOKEN="test-only", PYTHONPATH=directory)
            def run():
                return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "RemoteSigned", "-File", str(entry)],
                    capture_output=True, text=True, errors="replace", timeout=60, env=env)
            def health():
                with urlopen(f"http://127.0.0.1:{port}/healthz",timeout=3) as response:
                    return json.load(response)
            try:
                first = run()
                self.assertEqual(first.returncode, 0, first.stderr)
                self.assertIn("PRIVATE_LAUNCH_ATTEMPTED", first.stdout)
                identity = health()
                self.assertFalse(identity["leaked"])
                second = run()
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertEqual(health()["pid"], identity["pid"])
            finally:
                # Only terminate the process belonging to the isolated temporary app.
                script = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -like '*tradingagents.forecast_lab.public_app:app*' "
                    "-and $_.CommandLine.Contains($env:FIXTURE_PROJECT) } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
                subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
                               env=dict(env,FIXTURE_PROJECT=str(project / "packages")),check=True)
            with socket.socket() as foreign:
                foreign.bind(("127.0.0.1", int(port)))
                foreign.listen(1)
                blocked = run()
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn("PRIVATE_LAUNCH_ATTEMPTED", blocked.stdout)
                self.assertIn("different listener", blocked.stderr)
