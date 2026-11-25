"""Exercise the actual integrated bundle with the server's anonymous HTML marker."""
import functools
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DIST = Path(os.environ.get("FORECAST_PUBLIC_UI_DIST", "apps/web/dist"))
CHROME = next((x for x in (os.environ.get("CHROME_BIN"), shutil.which("chromium"),
    shutil.which("google-chrome"), r"C:\Program Files\Google\Chrome\Application\chrome.exe") if x and Path(x).is_file()), None)


@unittest.skipUnless(os.environ.get("FORECAST_PUBLIC_UI_DIST") and CHROME and (DIST / "index.html").exists(), "requires Chromium and a built Forecast Lab bundle")
class IntegratedPublicViewerTests(unittest.TestCase):
    def test_anonymous_reads_with_stale_admin_state(self):
        forbidden = []
        checks = """
        (async()=>{
          const errors=[];
          async function wait(test) {for(let i=0;i<100;i++){if(test())return;await new Promise(r=>setTimeout(r,25));}throw Error(location.hash);}
          async function visit(hash,test){location.hash=hash;await wait(test);}
          function check(ok,label){if(!ok)errors.push(label);}
          try {
            await wait(()=>document.querySelector('.workspace'));
            check(!document.querySelector('.desktop-rail a[href="#/auth"]'),'admin menu');
            await visit('#/research/29',()=>document.querySelector('.evidence h2')?.textContent.includes('삼성전자'));
            check(document.querySelector('.headline').textContent.includes('61.0%'),'published probability');
            await wait(()=>document.querySelectorAll('.register a').length===3);
            const [first,partial,unissued]=document.querySelectorAll('.register a');
            check(partial.textContent.includes('일부 방법 발행') && !partial.textContent.includes('발행 대기') &&
              unissued.textContent.includes('발행 대기') && first.textContent.includes('채점 완료'),'partial vs unissued');
            check(document.querySelector('.condition').textContent.includes('75,000원') &&
              document.querySelector('.condition').textContent.includes('충족'),'frozen condition');
            check(document.querySelector('.news a')?.textContent.includes('당시 확인된 공시') &&
              document.querySelector('.news small').textContent.includes('시간 미상'),'archived news precision');
            check(document.documentElement.scrollWidth<=innerWidth,'research overflow');
            await visit('#/results',()=>document.querySelector('iframe')?.src.endsWith('#results'));
            await visit('#/schedules',()=>document.querySelector('main a[href="#/schedules/spy"]'));
            check(!document.querySelector('#addScheduleBtn, .op-cancel'),'schedule actions');
            await visit('#/schedules/SPY',()=>document.querySelector('main')?.innerText.includes('세부 실행 로그'));
            await visit('#/live',()=>document.querySelector('main')?.innerText.includes('공개 화면에서는 실행 종목'));
            await visit('#/retrospective',()=>document.querySelector('.review-empty'));
            check(!document.querySelector('.review-empty button'),'retrospective actions');
            await visit('#/portfolio?setup=1',()=>document.body.innerText.includes('공개할 포트폴리오'));
            check(!document.querySelector('dialog[open], .modal-overlay'),'account setup');
            await visit('#/reports/7',()=>document.querySelector('.report-meta'));
            check(document.querySelector('main h2').textContent.includes('SPY'),'legacy numeric report');
            await visit('#/auth',()=>location.hash==='#/');
            check(!document.querySelector('#tokenInput'),'auth');
            check(!window.socketCalls,'websocket');
            check(localStorage.getItem('gant_admin_token')==='stale-test-only','stale token modified');
            check(document.documentElement.scrollWidth<=innerWidth,'overflow');
          }catch(e){errors.push(String(e));}
          const o=document.createElement('output');o.id='result';o.textContent=errors.join('/')||'passed';document.body.replaceChildren(o);
        })()
        """
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                path = urlsplit(self.path).path
                if self.headers.get("Authorization") or "/events" in path or "retry-candidates" in path or path.startswith("/ws/"):
                    forbidden.append(path)
                if path == "/":
                    html = (DIST / "index.html").read_text(encoding="utf8").replace("<head>", '<head><meta name="forecast-console-access" content="public-readonly"><script>localStorage.setItem("gant_admin_token","stale-test-only");window.socketCalls=0;window.WebSocket=class{constructor(){window.socketCalls++}}</script>')
                    raw = html.replace("</body>", "<script>"+checks+"</script></body>").encode()
                    content = "text/html; charset=utf-8"
                elif path.startswith("/api/cases"):
                    row=dict(id=29,ticker="005930.KS",market="kr",data_session="2026-11-02",status="matured",forecast_probabilities={"single":0.61})
                    detail={**row,"arms":[{"method":"single","status":"published","probability":.61}],
                            "outcome":{"status":"scored","actual":1},"snapshot":{"currency":"KRW"},
                            "hypothesis":{"currency":"KRW","conditions":[{"id":"breakout","metric":"exit_close","operator":"gt","threshold":75000,"status":"met","observed_value":76000}]},
                            "issues":{"status":"available","items":[{"title":"당시 확인된 공시","publisher":"공시 자료","url":"https://example.org/release","published_precision":"day","published_day":"2026-11-01"}]}}
                    partial={**row,"id":28,"status":"pending","forecast_probabilities":{"single":0.0}}
                    unissued={**row,"id":27,"status":"pending","forecast_probabilities":{}}
                    raw=json.dumps([row,partial,unissued] if path=="/api/cases" else detail).encode()
                    content="application/json"
                elif path.startswith(("/workspace-api/", "/public-api/")):
                    data = {"/workspace-api/schedules":[{"ticker":"SPY","interval_days":1}],
                            "/workspace-api/schedules/SPY/cycles":[{"id":2,"scheduled_cycle":3,"status":"done","created_at":"2026-11-01T00:00:00Z"}],
                            "/workspace-api/portfolio/config":{"config":None},
                            "/workspace-api/reports":[{"ticker":"SPY","id":7,"final_trade_decision":"QA","created_at":"2026-11-01T00:00:00Z"}],
                            "/public-api/reports/7":{"ticker":"SPY","id":7},
                            "/workspace-api/queue":{"running":"SPY","pending":[],"total":1},
                            "/workspace-api/metrics":{"by_currency":{}},
                            "/workspace-api/tickers/names":{}}.get(path,[])
                    raw=json.dumps(data).encode()
                    content="application/json"
                elif path.startswith("/research/"):
                    raw=b"<html><body>Research</body></html>" if path=="/research/" else b""
                    content="text/html" if path=="/research/" else "text/css"
                else:
                    return super().do_GET()
                self.send_response(200);self.send_header("Content-Type",content);self.end_headers()
                try:
                    self.wfile.write(raw)
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                    pass

        server=ThreadingHTTPServer(("127.0.0.1",0),functools.partial(Handler,directory=str(DIST)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
                for width in [393,1440]:
                    with self.subTest(width=width):
                        url=f"http://127.0.0.1:{server.server_port}/"
                        dom=subprocess.run([CHROME,"--headless=new","--disable-gpu","--no-first-run","--no-proxy-server",
                            "--virtual-time-budget=12000",f"--window-size={width},900",f"--user-data-dir={root}/{width}",
                            "--dump-dom",url],capture_output=True,encoding="utf8",errors="replace",timeout=35,check=True).stdout
                        self.assertIn('<output id="result">passed</output>',dom[-500:])
            self.assertEqual(forbidden,[])
        finally:
            server.shutdown();server.server_close()
