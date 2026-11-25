import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradingagents.forecast_lab.console import mount_frontend
from tradingagents.forecast_lab.public_app import create_app


class ForecastLabInstallAssetsTests(unittest.TestCase):
    def test_public_and_private_install_contract(self):
        source = Path(__file__).resolve().parents[1] / "apps/web/lab-pwa"
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp)
            for asset in source.iterdir():
                shutil.copyfile(asset, dist / asset.name)
            (dist / "index.html").write_text("<html><head></head></html>",encoding="utf-8")
            (dist / "other.png").write_bytes(b"should not be public")
            public = TestClient(create_app(reader=lambda path: [], dist=dist))
            private_app = FastAPI()
            mount_frontend(private_app, dist)
            private = TestClient(private_app)
            for client in (public, private):
                favicon = client.get("/favicon.svg")
                self.assertEqual(favicon.status_code, 200)
                self.assertIn("image/svg+xml", favicon.headers["content-type"])
                self.assertEqual(favicon.content, (source / "favicon.svg").read_bytes())
                manifest = client.get("/gant.webmanifest")
                self.assertEqual(manifest.status_code, 200)
                self.assertEqual(manifest.headers["content-type"], "application/manifest+json")
                self.assertEqual(manifest.headers["cache-control"], "no-cache")
                spec = json.loads(manifest.content)
                self.assertEqual(spec["start_url"], "/#/reports")
                self.assertEqual(spec["scope"], "/")
                self.assertEqual(spec["display"], "standalone")
                self.assertEqual(
                    {(i["sizes"],i["purpose"]) for i in spec["icons"]},
                    {(s,p) for s in ("192x192","512x512") for p in ("any","maskable")},
                )
                icons = [(i["src"],int(i["sizes"].split("x")[0])) for i in spec["icons"]]
                for path, size in [*icons, ("/apple-touch-icon.png",180)]:
                    image = client.get(path)
                    self.assertEqual(image.headers["content-type"], "image/png")
                    self.assertEqual(image.content[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual(struct.unpack(">II",image.content[16:24]), (size,size))
                worker = client.get("/gant-sw.js")
                self.assertEqual(worker.status_code, 200)
                self.assertEqual(worker.headers["service-worker-allowed"], "/")
                self.assertEqual(worker.headers["cache-control"], "no-cache")
                self.assertNotIn("caches.", worker.text)
            csp = public.get("/").headers["content-security-policy"]
            self.assertIn("manifest-src 'self'", csp)
            self.assertIn("worker-src 'self'", csp)
            self.assertEqual(public.get("/other.png").status_code, 404)
            self.assertEqual(public.post("/gant-sw.js").status_code, 405)
