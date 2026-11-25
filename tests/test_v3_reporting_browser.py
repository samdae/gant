"""Exercise report selection, archive isolation and populated native results in Chromium."""

import functools
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from test_integrated_public_viewer import CHROME, DIST


@unittest.skipUnless(
    CHROME and os.getenv("FORECAST_PUBLIC_UI_DIST") and (DIST / "index.html").exists(),
    "requires an external candidate bundle and Chromium",
)
class ReportingBrowserTests(unittest.TestCase):
    def test_round_trip_and_delayed_archive(self):
        setup = """
        const getAsset=window.fetch.bind(window);
        let resolveFirst;
        window.releaseFirst=()=>resolveFirst?.();
        const json=(value)=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
        const row={ticker:'NVDA',market:'us',id:1,data_session:'2026-11-24',status:'pending',forecast_probabilities:{single:.39}};
        const report=id=>({ticker:'NVDA',id,created_at:'2026-11-24T03:00:00Z',scheduled_cycle:id,final_trade_decision:'회차 판단 '+id});
        window.fetch=async (url, options)=>{
          const u=new URL(url,location.href),p=u.pathname;
          if(p==='/api/cases')return json([row]);
          if(p==='/api/report-sources/8') await new Promise(r=>resolveFirst=r);
          if(p.startsWith('/api/report-sources/')) {
            const id=Number(p.split('/').at(-1)), date='2026-11-24T03:00:00Z';
            const items=[{title:'회차 자료 '+id,publisher:'테스트 매체',url:'https://example.org/post',
              published_at:date,first_seen_at:date}];
            items.push({...items[0],title:"추가 자료 "+id});
            return json({id,ticker:'NVDA',as_of:date,issues:{status:'available',items},last30days:{status:'uncollected',items:[]}});
          }
          if(p==='/workspace-api/reports/tickers')return json([{ticker:'NVDA',report_count:2,latest_at:'2026-11-24T03:00:00Z'}]);
          if(p==='/workspace-api/reports')return json([report(8),report(7)]);
          if(p==='/api/status')return json({tickers:[{ticker:'NVDA',market:'us',classification:{asset_class:'equity',sector:'technology'}}],progress:{phase:'idle'}});
          if(p==='/api/stats'){
            const r={control:'baseline',treated:'single',method:'single',n:3,control_brier:.24,treated_brier:.2,improvement:.04,lower:.4,upper:.6,mean_probability:.51,observed_rate:.67};
            return json({comparisons:[r],reference_comparisons:[],calibration:[r],sector_by_basis:[],counts:{matured:u.searchParams.has('from_date')?2:3},sector_coverage:{}});
          }
          if(p.startsWith('/workspace-api/'))return json({});
          return getAsset(url,options);
        };
        """
        verify = """
        (async()=>{
          const wait=async (fn)=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,30));}throw Error(location.hash+' '+document.querySelector('main')?.innerText.slice(-120));}
          const q=s=>document.querySelector(s);
          try {
            location.hash='#/reports';
            await wait(()=>q('.forecast-reports a[href="#/research/1"]')?.textContent.includes('39.0%'));
            const ledger=q('.forecast-reports'), estimate=q('.forecast-reports .figure strong');
            if(getComputedStyle(ledger).backgroundColor!=='rgb(32, 33, 36)' ||
              getComputedStyle(estimate).color!=='rgb(195, 169, 255)') throw Error('forecast ledger theme');
            await wait(()=>q('.round-picker button'));
            q('.round-picker button').click();
            await wait(()=>q('.rounds a[href$="report=8"]'));
            q('.rounds a[href$="report=8"]').click();
            await wait(()=>q('#cycle-select') && q('.archive') && resolveFirst);
            q('#cycle-select').click(); await wait(()=>q('.select-option:not(.active)'));
            q('.select-option:not(.active)').click(); await wait(()=>q('.archive')?.innerText.includes('회차 자료 7'));
            if(!q('.archive .source h4')?.textContent.includes('last30days') || q('.archive').innerText.includes('추가 자료 7'))throw Error('archive preview order');
            if(!(q('.desk-conclusion').compareDocumentPosition(q('.archive')) & Node.DOCUMENT_POSITION_FOLLOWING))throw Error('conclusion not first');
            q('.archive button[aria-expanded=false]').click(); await wait(()=>q('.archive').innerText.includes('추가 자료 7'));
            releaseFirst(); await new Promise(r=>setTimeout(r,100));
            if(q('.archive').innerText.includes('회차 자료 8'))throw Error('stale archive');
            location.hash='#/results'; await wait(()=>q('.review')?.innerText.includes('0.240 → 0.200'));
            const start=q('.review input[type=date]');start.value='2026-11-01';start.dispatchEvent(new Event('input',{bubbles:true}));
            await wait(()=>q('.counts')?.innerText.includes('2'));
            location.hash='#/observe'; await wait(()=>q('.review tbody')?.innerText.includes('정보기술'));
            if(document.documentElement.scrollWidth>innerWidth)throw Error('horizontal overflow');
            document.body.innerHTML='<output id="pass">verified</output>';
          }catch(e){document.body.innerText='report-test '+e;}
        })();
        """

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/":
                    return super().do_GET()
                page = (DIST / "index.html").read_text(encoding="utf8")
                page = page.replace(
                    "<head>",
                    '<head><meta name="forecast-console-access" content="public-readonly"><script>'
                    + setup
                    + "</script>",
                )
                raw = page.replace(
                    "</body>", "<script>" + verify + "</script></body>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(DIST))
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for width in (390, 1440):
                with (
                    self.subTest(width=width),
                    tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile,
                ):
                    args = [
                        CHROME,
                        "--headless=new",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-proxy-server",
                        "--virtual-time-budget=15000",
                        f"--window-size={width},900",
                        f"--user-data-dir={profile}",
                        "--dump-dom",
                        f"http://127.0.0.1:{server.server_port}/",
                    ]
                    dom = subprocess.run(
                        args,
                        capture_output=True,
                        timeout=50,
                        encoding="utf8",
                        errors="replace",
                        check=True,
                    ).stdout
                    self.assertIn('<output id="pass">verified</output>', dom[-700:])
        finally:
            server.shutdown()
            server.server_close()
