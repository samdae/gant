"""Verify report semantics and untrusted response envelopes in a real browser DOM."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "packages/tradingagents/forecast_lab/web"


def browser():
    candidates = [
        os.environ.get("CHROME_BIN"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


def browser_check(cases):
    """Run with supplied API-shaped cases without contacting a scheduler, DB, or model."""
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        src = (WEB / "lab.js").read_text(encoding="utf-8")
        html = (WEB / "index.html").read_text(encoding="utf-8")
        fixture_data = json.dumps(cases, ensure_ascii=False).replace("<", r"\u003c")
        checks = r"""
        const fixture = CASE_DATA;
        const result = [];
        for (const c of fixture) {
            renderCase($("detail"), c);
            const d = $("detail");
            const text = d.textContent;
            const leaks = text.match(/\*\*|```|snapshot_sha256|input_sha256|strategy_json|forecast_5s|secret_key|create_bull_researcher|\[object Object\]/g) || [];
            if (leaks.length) result.push(c.id + " leaked " + leaks.join(","));
            if (d.querySelector("script,img,iframe,[onerror]") || window.pwned) result.push("executable markup");
            if (document.body.scrollWidth > window.innerWidth) result.push("mobile overflow");
            if (c.id === 8888) {
                for (const sel of ["strong","ul li","ol li","h5","blockquote","table","details > summary"]) {
                    if (!d.querySelector(".report " + sel) && !d.querySelector(sel)) result.push("missing " + sel);
                }
                if (!text.includes("제안 비중") || !text.includes("동결된 시장 근거") || !text.includes("상승 확률 70.0%"))
                    result.push("incomplete structured report");
                if (text.includes("SHOULD_NEVER_RENDER")) result.push("tool trace leaked");
            }
        }
        const resultNode = document.createElement("output");
        resultNode.id = "dom-result";
        resultNode.textContent = result.length ? result.join(" / ") : "passed";
        document.body.replaceChildren(resultNode);
        """.replace("CASE_DATA", fixture_data)
        # Mock HTTP before running the normal script. A never-resolving fetch keeps the
        # periodic refresh out of this synchronous DOM renderer check.
        html = html.replace(
            '<link rel="stylesheet" href="/lab.css" />',
            "<style>" + (WEB / "lab.css").read_text(encoding="utf-8") + "</style>",
        )
        html = html.replace('<script defer src="/lab.js"></script>', "")
        html = html.replace(
            "</body>",
            "<script>window.fetch=()=>new Promise(()=>{});</script><script>"
            + src
            + "</script><script>"
            + checks
            + "</script></body>",
        )
        file = folder / "report.html"
        file.write_text(html, encoding="utf-8")
        r = subprocess.run(
            [
                browser(),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--window-size=420,800",
                "--user-data-dir=" + str(folder / "profile"),
                "--dump-dom",
                file.as_uri(),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            check=True,
        )
        marker = '<output id="dom-result">'
        return (
            r.stdout.rsplit(marker, 1)[-1].split("</output>", 1)[0]
            if marker in r.stdout
            else "browser failed to execute checks"
        )


@unittest.skipUnless(browser(), "A Chromium browser is required")
class LabWebTest(unittest.TestCase):
    def test_nested_reports_and_no_executable_markup(self):
        narrative = (
            "### 투자 근거\n\n**강조된 문장**\n\n- 이유 하나\n- 이유 둘\n\n1. 첫 항목\n2. 다음 항목\n\n"
            "> 가격 근거\n\n|지표|값|\n|---|---|\n|거래량|100|\n\n<img src=x onerror=window.pwned=1>\n\n"
            "```strategy_json\n"
            + json.dumps(
                {
                    "action": "BUY",
                    "conviction": "HIGH",
                    "allocation_pct": 35,
                    "forecast_5s": {"p_up": 0.7},
                    "secret_key": "SHOULD_NEVER_RENDER",
                }
            )
            + "\n```"
        )
        envelope = json.dumps(
            {
                "content": [{"type": "text", "text": narrative}],
                "calls": [{"arguments": {"secret_key": "SHOULD_NEVER_RENDER"}}],
            }
        )
        c = {
            "id": 8888,
            "ticker": "TEST",
            "market": "us",
            "status": "awaiting",
            "snapshot": {"features": {}, "currency": "USD", "bars": []},
            "arms": [
                {
                    "method": "debate",
                    "status": "published",
                    "probability": 0.7,
                    "rationale": envelope,
                    "audit": {
                        "snapshot_sha256": "SHOULD_NEVER_RENDER",
                        "debate": [
                            {"role": "create_bull_researcher", "output": envelope}
                        ],
                    },
                }
            ],
        }
        self.assertEqual(browser_check([c]), "passed")
