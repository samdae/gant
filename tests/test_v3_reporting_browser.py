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
        window.statsQueries=[];
        window.caseQueries=[];
        window.releaseFirst=()=>resolveFirst?.();
        const json=(value)=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
        const row={ticker:'NVDA',market:'us',id:1,data_session:'2026-11-24',status:'pending',forecast_probabilities:{single:.39}};
        const report=id=>({ticker:'NVDA',id,created_at:'2026-11-24T03:00:00Z',scheduled_cycle:id,final_trade_decision:'회차 판단 '+id});
        window.fetch=async (url, options)=>{
          const u=new URL(url,location.href),p=u.pathname;
          if(p==='/api/cases') {
            window.caseQueries.push(Object.fromEntries(u.searchParams));
            return json(u.searchParams.get('from_date')==='2026-11-05' ? [] : [row]);
          }
          if(p==='/api/cases/1')return json({...row,arms:[],snapshot:{}});
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
            window.statsQueries.push(Object.fromEntries(u.searchParams));
            if(window.holdStats){
              window.holdStats=false;
              const ok=await new Promise(resolve=>window.respondStats=resolve);
              window.respondStats=null;
              if(!ok)return new Response('',{status:503});
            }
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
            const expectedControlHeight = matchMedia('(max-width: 767px)').matches ? 44 : 40;
            for (const selector of ['.desk-search','.report-kind button','.round-picker button']) {
              const element=q(selector), box=element.getBoundingClientRect();
              if (Math.abs(box.height-expectedControlHeight)>1 || getComputedStyle(element).borderRadius!=='7px')
                throw Error(selector+' control '+box.height+' / '+getComputedStyle(element).borderRadius);
            }
            q('.round-picker button').click();
            await wait(()=>q('.rounds a[href$="report=8"]'));
            q('.rounds a[href$="report=8"]').click();
            await wait(()=>q('#cycle-select') && q('.archive') && resolveFirst);
            q('#cycle-select').click(); await wait(()=>q('[role=option][aria-selected=false]'));
            q('[role=option][aria-selected=false]').click(); await wait(()=>q('.archive')?.innerText.includes('회차 자료 7'));
            if(!q('.archive .source h4')?.textContent.includes('last30days') || q('.archive').innerText.includes('추가 자료 7'))throw Error('archive preview order');
            if(!(q('.desk-conclusion').compareDocumentPosition(q('.archive')) & Node.DOCUMENT_POSITION_FOLLOWING))throw Error('conclusion not first');
            q('.archive button[aria-expanded=false]').click(); await wait(()=>q('.archive').innerText.includes('추가 자료 7'));
            releaseFirst(); await new Promise(r=>setTimeout(r,100));
            if(q('.archive').innerText.includes('회차 자료 8'))throw Error('stale archive');
            window.holdStats=true;
            location.hash='#/results';
            await wait(()=>window.respondStats && q('.review .pending[role=status]') && q('.refresh:disabled'));
            if(q('.review .counts') || q('.refresh').getAttribute('aria-busy')!=='true')throw Error('false initial results');
            window.respondStats(true);
            await wait(()=>q('.review')?.innerText.includes('0.240 → 0.200') && !q('.refresh').disabled);
            const refreshBox=q('.refresh').getBoundingClientRect();
            window.holdStats=true;
            q('.refresh').click();
            await wait(()=>window.respondStats && q('.refresh:disabled'));
            if(!q('.review').innerText.includes('0.240 → 0.200') ||
                q('.refresh').getBoundingClientRect().width!==refreshBox.width)throw Error('refresh layout/data changed');
            window.respondStats(false);
            await wait(()=>q('.review [role=alert]')?.innerText.includes('마지막 조회') && !q('.refresh').disabled);
            if(!q('.review').innerText.includes('0.240 → 0.200'))throw Error('discarded previous stats');
            q('.refresh').click();
            await wait(()=>!q('.review [role=alert]') && !q('.refresh').disabled);
            const before=statsQueries.length, trigger=q('.review .range-trigger');
            trigger.click();
            await wait(()=>q('.range-dialog[open] .navigation'));
            q('.range-dialog [aria-label="연도와 월 선택"]').click();
            await wait(()=>q('.range-dialog input'));
            const year=q('.range-dialog input');
            year.value='2026'; year.dispatchEvent(new Event('input',{bubbles:true}));
            [...document.querySelectorAll('.range-dialog .months button')].find(b=>b.textContent==='11월').click();
            await wait(()=>q('[data-day="2026-11-23"]'));
            q('[data-day="2026-11-23"]').click(); await Promise.resolve();
            if(statsQueries.length!==before || !q('.range-dialog[open]'))throw Error('draft committed');
            q('[data-day="2026-11-01"]').click();
            await wait(()=>q('.counts')?.innerText.includes('2') && statsQueries.at(-1)?.from_date==='2026-11-01');
            if(statsQueries.at(-1).to_date!=='2026-11-23' || q('.range-dialog[open]') ||
              !location.hash.includes('to_date=2026-11-23'))throw Error('reversed range');
            trigger.click(); q('[data-day="2026-11-01"]').click(); q('[data-day="2026-11-01"]').click();
            await wait(()=>statsQueries.at(-1)?.to_date==='2026-11-01');
            location.hash='#/observe'; await wait(()=>q('.review tbody')?.innerText.includes('정보기술'));
            location.hash='#/research/1?market=us&from_date=2026-11-01';
            await wait(()=>q('.evidence h2')?.textContent.includes('엔비디아'));
            q('.choose').click();
            const openCalendar=()=>q('dialog[open] .range-trigger').click();
            const day=value=>q('.range-dialog[open] [data-day="'+value+'"]');
            openCalendar();await wait(()=>day('2026-11-03'));
            const listBefore=caseQueries.length;
            day('2026-11-03').click();day('2026-11-01').click();
            await wait(()=>document.activeElement.matches('dialog[open] .range-trigger') && caseQueries.at(-1)?.to_date==='2026-11-03');
            if(caseQueries.length!==listBefore+1)throw Error('duplicate detail-to-list request');
            openCalendar();await wait(()=>day('2026-11-05'));
            day('2026-11-05').click();day('2026-11-05').click();
            await wait(()=>caseQueries.at(-1)?.from_date==='2026-11-05' && q('dialog[open]')?.innerText.includes('공개된 연구 사례가 없습니다'));
            if(caseQueries.length!==listBefore+2 || caseQueries.at(-1)?.to_date!=='2026-11-05')throw Error('same-path range did not refetch once');
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
            for width in (360, 393, 1440):
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
