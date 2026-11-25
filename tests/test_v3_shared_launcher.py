"""Exercise both Windows shared launch paths without touching the real ports or runtime."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "Windows launcher")
class SharedLauncherTests(unittest.TestCase):
    def test_both_roles_survive_repeat_watchdog_and_drop_private_environment(self):
        with tempfile.TemporaryDirectory(prefix="shared viewer ") as directory:
            root = Path(directory)
            runtime = root / "TradingAgentsV3"
            (runtime / "shared-read").mkdir(parents=True)
            (runtime / "shared-viewer.enabled").touch()
            (runtime / "shared-read/logins.json").write_text("{}")
            scripts = root / "scripts"
            scripts.mkdir()
            package = root / "packages/tradingagents/forecast_lab"
            package.mkdir(parents=True)
            (package.parent / "__init__.py").touch()
            (package / "__init__.py").touch()
            (package / "shared_view.py").write_text("""import os
from fastapi import FastAPI
def instance(role):
    app = FastAPI()
    @app.get('/healthz')
    def health():
        return dict(ok=True, source='v2',role=role,pid=os.getpid(),
                    secret='PRIVATE_ADMIN_TOKEN' in os.environ, config='GANT_SHARED_READ_CONFIG' in os.environ)
    return app
def build_shared_core(): return instance('core')
def build_shared_edge(): return instance('edge')
""")
            with socket.socket() as a, socket.socket() as b:
                a.bind(("127.0.0.1", 0))
                b.bind(("127.0.0.1", 0))
                core, edge = a.getsockname()[1], b.getsockname()[1]
            for name in ("start-forecast-lab-services.ps1", "start-forecast-lab.ps1", "start-forecast-lab-public.ps1",
                         "start-v3-shared-view.ps1", "spawn-forecast-lab-public.py", "spawn-v3-shared-view.py"):
                src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
                src = src.replace("8024", str(core)).replace("8025", str(edge))
                src = src.replace("Join-Path $project '.venv/Scripts/python.exe'", "'" + sys.executable.replace("'", "''") + "'")
                (scripts / name).write_text(src, encoding="utf-8-sig")
            env = dict(os.environ, LOCALAPPDATA=directory, PRIVATE_ADMIN_TOKEN="test-only",
                       FIXTURE_PROJECT=str(root / "packages"))
            def run():
                return subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","RemoteSigned",
                    "-File",str(scripts / "start-forecast-lab-services.ps1")], capture_output=True,
                    encoding="utf-8", errors="replace", timeout=100, env=env)
            def health(port):
                with urlopen(f"http://127.0.0.1:{port}/healthz",timeout=4) as response:
                    return json.load(response)
            try:
                first = run()
                self.assertEqual(first.returncode, 0, first.stderr)
                rows = [health(core), health(edge)]
                self.assertEqual([r["role"] for r in rows], ["core","edge"])
                self.assertEqual([r["config"] for r in rows], [True, False])
                self.assertTrue(all(not r["secret"] for r in rows))
                second = run()
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertEqual(rows, [health(core),health(edge)])
            finally:
                script = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -like '*tradingagents.forecast_lab.shared_view:build_shared_*' "
                    "-and $_.CommandLine.Contains($env:FIXTURE_PROJECT) } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
                subprocess.run(["powershell.exe","-NoProfile","-Command",script],env=env,check=True)
