"""Check the built Forecast Lab console against local, read-only fixtures in headless Chrome.

Usage: python scripts/check-forecast-review-layout.py PATH_TO_LAB_DIST [--screenshots DIR]
Requires websocket-client (in the project environment) and Chrome (or set CHROME_PATH).
"""

import argparse
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

import websocket


def fixture_response(path, populated):
    position = dict(position_id=42, ticker="SPY", shares=10, avg_cost=500,
                    current_price=510, pnl=100, return_pct=2, closed_at="2026-11-17")
    reflection = dict(id=7, position_id=42, ticker="SPY", outcome="win",
                      return_pct=2, created_at="2026-11-18")
    names = {"SPY": "SPDR S&P 500 ETF Trust Long Instrument Name Fixture"}
    unknown = {**position, "ticker": "QAUNKNOWN", "position_id": 77}
    routes = {
        "tickers/names": names,
        "positions/market": [position, unknown],
        "positions/closed": [position],
        "reflections": [reflection],
        "reflections/retry-candidates": [],
        "metrics": {"by_currency": {}},
        "portfolio/config": {"enabled": False},
    }
    data = routes.get(path, [])
    return [] if not populated and isinstance(data, list) else data


class Fixtures(SimpleHTTPRequestHandler):
    populated = True

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/research/workspace-tokens.css":
            assets = Path(__file__).resolve().parents[1] / "packages/tradingagents/forecast_lab/web"
            body = (assets / "workspace-tokens.css").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.end_headers()
            self.wfile.write(body)
            return
        if not path.startswith(("/workspace-api/", "/api/")):
            return super().do_GET()
        body = json.dumps(fixture_response(path.split("/", 2)[2], self.populated)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class Chrome:
    def __init__(self, profile, executable):
        self.process = subprocess.Popen(
            [executable, "--user-data-dir=" + str(profile), "--headless=new",
             "--disable-gpu", "--disable-background-networking", "--no-proxy-server",
             "--remote-debugging-port=0", "--remote-allow-origins=*", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        port_file = profile / "DevToolsActivePort"
        for _ in range(120):
            if port_file.exists():
                break
            time.sleep(.1)
        port = port_file.read_text().splitlines()[0]
        with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
            target = next(t for t in json.load(response) if t["type"] == "page")
        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10,
                                              suppress_origin=True)
        self.sequence = 0

    def call(self, method, **params):
        self.sequence += 1
        self.ws.send(json.dumps(dict(id=self.sequence, method=method, params=params)))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.sequence:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply["result"]

    def evaluate(self, expression):
        return self.call("Runtime.evaluate", expression=expression,
                         returnByValue=True)["result"].get("value")

    def wait(self, expression):
        for _ in range(100):
            if self.evaluate(f"Boolean({expression})"):
                return
            time.sleep(.1)
        raise AssertionError((expression, self.evaluate("document.body.innerText")))

    def close(self):
        self.ws.close()
        self.process.terminate()
        self.process.wait(timeout=10)


# ClientRects on an element can look correct even when individual Korean characters wrap.
GEOMETRY = """(() => {
  const buttons = [...document.querySelectorAll(".review-switch button")];
  const issues = [];
  const bounds = el => {
    const range = document.createRange();
    range.selectNodeContents(el);
    return [...range.getClientRects()];
  };
  for (const button of buttons) {
    const label = button.querySelector("span");
    const labelRects = bounds(label);
    const badge = button.querySelector("small");
    if (labelRects.length !== 1) issues.push(label.textContent + " wrapped");
    if (badge) {
      const counts = bounds(badge);
      const mid = r => r.top + r.height / 2;
      if (counts.length !== 1 || Math.abs(mid(counts[0]) - mid(labelRects[0])) > 2)
        issues.push(label.textContent + " count wrapped");
    }
    const rect = button.getBoundingClientRect();
    if (rect.right > innerWidth || labelRects.some(r => r.right > rect.right + 1))
      issues.push(label.textContent + " clipped");
  }
  if (document.documentElement.scrollWidth > innerWidth) issues.push("page overflow");
  return issues;
})()"""


def check_selection_and_evidence(browser, base):
    # This fixture answers requests in the browser. No local service or database is contacted.
    browser.call("Page.addScriptToEvaluateOnNewDocument", source="""(() => {
      const original = window.fetch;
      const json = x => new Response(JSON.stringify(x), { headers: { "Content-Type":"application/json" }});
      window.pendingPositions = {};
      window.posts = [];
      const report = { id: 61, ticker:"QA", created_at:"2026-11-15T12:00:00Z",
        stored_decision_position:null, decision_position:"BUY", portfolio_action:"SELL",
        portfolio_shares:0, final_trade_decision:"분석 기록", execution_trades:[] };
      const filled = {...report, id:60, created_at:"2026-11-14T12:00:00Z", stored_decision_position:"BUY",
        portfolio_shares:0.000102, execution_trades:[{action:"SELL",shares:0.0001,price:345.67,currency:"USD",
        executed_at:"2026-11-15T12:30:00Z"}] };
      window.fetch = async (url, options) => {
        const path = new URL(url, location.origin).pathname.replace("/workspace-api", "");
        if (path === "/retrospective/analyze") {
          window.posts.push(JSON.parse(options.body));
          return new Promise(resolve => { window.finishPost = () => resolve(json({enqueued:[11]})); });
        }
        if (path === "/retrospective/tickers") return json(["AAA","BBB"].map(ticker=>({ticker,has_trades:true})));
        if (path.startsWith("/retrospective/positions/")) {
          const ticker = path.split("/").pop();
          return new Promise(resolve => {
            (window.pendingPositions[ticker] ||= []).push(id => resolve(json([{position_id:id,
              ticker,position_sequence:id,pos_status:"active", opened_at:"2026-11-14",retro_status:null}])));
          });
        }
        if (path === "/reports") return json([report,filled]);
        return original(url,options);
      };
    })()""")
    browser.call("Page.navigate", url=base + "/#/retrospective")
    button = ".analysis-tab-row button"
    chip = ".modal-tickers button"
    submit = ".modal-footer button"
    def click(selector, index=0):
        expr = f"document.querySelectorAll({json.dumps(selector)})[{index}]"
        browser.wait(expr)
        browser.evaluate(f"{expr}.click()")

    click(button)
    click(chip)
    browser.wait("pendingPositions.AAA?.length === 1")
    click(chip, 1)
    browser.wait("pendingPositions.BBB?.length === 1")
    browser.evaluate("pendingPositions.BBB.shift()(22)")
    browser.wait("document.querySelector('.modal-pos-row')?.innerText.includes('22회차')")
    browser.evaluate("pendingPositions.AAA.shift()(11)")
    click(submit)
    browser.wait("posts.length === 1")
    assert browser.evaluate("posts[0]") == {"mode":"ticker","ticker":"BBB","position_ids":[22]}
    click(".modal-close")
    click(button)
    click(chip)
    browser.wait("pendingPositions.AAA.length === 1")
    browser.evaluate("finishPost()")
    click(".modal-close")
    click(button)
    browser.evaluate("pendingPositions.AAA.shift()(11)")
    assert not browser.evaluate("document.querySelector('.modal-pos-row, .modal-message')")
    assert browser.evaluate("document.querySelector('.modal-footer button').disabled")

    for route in ("/reports/qa", "/trade/qa"):
        browser.call("Page.navigate", url=base + "/#" + route)
        browser.wait("document.querySelector('.evidence .fills')?.innerText.includes('연결된 체결 기록 없음')")
        facts = browser.evaluate("[...document.querySelector('.evidence').children].map(x=>x.innerText)")
        assert "미기록" in facts[0] and "매도" in facts[1] and "0주" in facts[1], facts
    click("#page-trade .review-switch button", 1)
    browser.wait("document.querySelector('.history-list')?.innerText.includes('345.67 USD')")
    history = browser.evaluate("document.querySelector('.history-list').innerText")
    assert "0.000102주" in history and "0.0001주" in history, history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if not (args.dist / "index.html").is_file():
        parser.error("Supply the directory containing the built Forecast Lab index.html")
    windows_chrome = Path(os.getenv("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe"
    executable = os.getenv("CHROME_PATH") or shutil.which("google-chrome") or str(windows_chrome)
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(Fixtures, directory=str(args.dist))) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
                browser = Chrome(Path(temp), executable)
                try:
                    browser.call("Page.enable")
                    browser.call("Network.enable")
                    browser.call("Network.setBlockedURLs", urls=["https://*", "http://localhost/*"])
                    for width in (320, 360, 390, 1440):
                        browser.call("Emulation.setDeviceMetricsOverride", width=width, height=900,
                                     deviceScaleFactor=1, mobile=width < 500)
                        for populated in (True, False):
                            Fixtures.populated = populated
                            for route in ("positions", "reflections", "trade/spy"):
                                browser.call("Page.navigate", url="about:blank")
                                browser.wait("location.href === 'about:blank'")
                                url = f"http://127.0.0.1:{server.server_port}/#/{route}"
                                browser.call("Page.navigate", url=url)
                                browser.wait("document.querySelector('.review-switch')")
                                if route == "trade/spy":
                                    browser.wait("document.querySelector('#page-trade .review-switch button span')")
                                    assert browser.evaluate(GEOMETRY) == [], (width, route)
                                    continue
                                ready = ".review-register tbody tr" if populated else (
                                    ".review-empty")
                                browser.wait(f"document.querySelector({json.dumps(ready)})")
                                if not populated:
                                    browser.wait("document.body.innerText.includes('없습니다')")
                                if route == "positions":
                                    browser.wait("document.querySelectorAll('.review-switch small').length === 2")
                                if populated:
                                    browser.wait("document.querySelector('.review-register .instrument .symbol')")
                                    assert browser.evaluate("""(() => {
                                      const label = document.querySelector('.review-register .instrument');
                                      const name = label.querySelector('.name');
                                      const symbol = label.querySelector('.symbol');
                                      return name.innerText.includes('Long Instrument Name Fixture')
                                        && symbol.innerText === 'SPY'
                                        && parseFloat(getComputedStyle(name).fontSize) >
                                           parseFloat(getComputedStyle(symbol).fontSize)
                                        && name.getBoundingClientRect().right <= innerWidth;
                                    })()"""), (width, route, "name-first label")
                                    if route == "positions":
                                        assert browser.evaluate("""(() => {
                                          const labels = [...document.querySelectorAll('.review-register .instrument')];
                                          return labels.some(el => el.innerText.trim() === 'QAUNKNOWN'
                                            && !el.querySelector('.symbol'));
                                        })()"""), "Unknown ticker must appear exactly once"
                                issues = browser.evaluate(GEOMETRY)
                                assert issues == [], (width, route, populated, issues)
                                if args.screenshots:
                                    # The route enters with a brief opacity transition.
                                    browser.call("Runtime.evaluate", expression="Promise.allSettled("
                                                 "document.getAnimations().filter(a => "
                                                 "a.effect?.getTiming().iterations === 1).map(a => a.finished))",
                                                 awaitPromise=True)
                                    state = "populated" if populated else "empty"
                                    name = f"{route}-{state}-{width}.png"
                                    shot = browser.call("Page.captureScreenshot", format="png")
                                    (args.screenshots / name).write_bytes(base64.b64decode(shot["data"]))
                    browser.call("Emulation.setDeviceMetricsOverride", width=360, height=900,
                                 deviceScaleFactor=1, mobile=True)
                    browser.call("Page.navigate", url=f"http://127.0.0.1:{server.server_port}/#/retrospective")
                    browser.wait("document.querySelector('.analysis-tab-row button')")
                    browser.evaluate("document.documentElement.style.fontSize = '20px'")
                    single_line = browser.evaluate("""(() => {
                      const group = document.querySelector('.analysis-tab-row');
                      const tabs = [...group.querySelectorAll('a')];
                      const action = group.querySelector('button');
                      return [...tabs, action].every(el => {
                        const r = document.createRange();
                        r.selectNodeContents(el);
                        return r.getClientRects().length === 1;
                      }) && tabs.every(el => el.offsetTop === tabs[0].offsetTop)
                        && action.getBoundingClientRect().right <= innerWidth
                        && document.documentElement.scrollWidth <= innerWidth;
                    })()""")
                    assert single_line, "Retrospective navigation wraps text at 125% font size"
                    browser.call("Page.navigate", url="about:blank")
                    browser.wait("location.href === 'about:blank'")
                    check_selection_and_evidence(browser, f"http://127.0.0.1:{server.server_port}")
                finally:
                    browser.close()
        finally:
            server.shutdown()
    print("Verified the position, reflection and trade detail controls in populated and empty views at 320, 360, 390, 1440 px.")


if __name__ == "__main__":
    main()
