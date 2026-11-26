"""Exercise report selection, archive isolation and populated native results in Chromium."""

import functools
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from test_integrated_public_viewer import BundleHandler, CHROME, DIST, DIST_BASE


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
        window.roundQueries=[];
        window.directoryRequests=0;
        window.releaseFirst=()=>resolveFirst?.();
        const json=(value)=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
        const row={ticker:'NVDA',market:'us',id:1,data_session:'2026-11-24',status:'pending',forecast_probabilities:{single:.39}};
        const latest={...row,id:201};
        const added={...row,id:203,data_session:'2026-11-25'};
        const other={...row,ticker:'WMT',id:202,data_session:'2026-11-21'};
        const report=id=>({ticker:'NVDA',id,created_at:'2026-11-24T03:00:00Z',scheduled_cycle:id,final_trade_decision:'회차 판단 '+id});
        window.fetch=async (url, options)=>{
          const u=new URL(url,location.href),p=u.pathname;
          if(p==='/api/forecast-tickers'){window.directoryRequests++;return json([directoryRequests>=3 ? added : latest,other]);}
          if(p==='/api/cases') {
            if(u.searchParams.has('ticker')){
              window.roundQueries.push(Object.fromEntries(u.searchParams));
              if(u.searchParams.get('ticker')==='WMT')return json([other]);
              const rounds=Array.from({length:201},(_,i)=>({...latest,id:201-i}));
              if(directoryRequests>=3)rounds.unshift(added);
              return json(rounds.filter(r=>r.id < Number(u.searchParams.get('before_id') || Infinity)).slice(0,200));
            }
            window.caseQueries.push(Object.fromEntries(u.searchParams));
            return json(u.searchParams.get('from_date')==='2026-11-05' ? [] : [row]);
          }
          if(p==='/api/cases/1' || p==='/api/cases/201' || p==='/api/cases/203'){
            const id=Number(p.split('/').at(-1));
            return json({...(id===203 ? added : row),id,arms:[{method:'single',status:'published',probability:id===1?.28:.39}],snapshot:{}});
          }
          if(p==='/api/report-sources/8') await new Promise(r=>resolveFirst=r);
          if(p.startsWith('/api/report-sources/')) {
            const id=Number(p.split('/').at(-1)), date='2026-11-24T03:00:00Z';
            const items=[{title:'회차 자료 '+id,publisher:'테스트 매체',url:'https://example.org/post',
              published_at:date,first_seen_at:date}];
            items.push({...items[0],title:"추가 자료 "+id,url:'https://example.org/more/'+id});
            const news_evidence=id===7 ? {version:1,status:'available',as_of:'2026-11-23T00:00:00Z',
              items:Array.from({length:42},(_,i)=>({...items[0],ref:'N'+(i+1),url:'https://example.org/frozen/'+i,
                source:i%2 ? 'last30days agent export' : 'Google News RSS',title:i===41 ? '인용된 제목' : '입력에만 보관된 제목 '+i})),
              analyst_cited:['N42'],decision_cited:['N42']} : null;
            return json({id,ticker:'NVDA',as_of:date,issues:{status:'available',items},last30days:{status:'uncollected',items:[]},news_evidence});
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
            await wait(()=>q('.round-picker button'));
            const reportTabs=()=>[...document.querySelectorAll('.report-kind button')];
            const selected=()=>q('.report-kind [aria-pressed=true]')?.textContent;
            if(reportTabs().map(b=>b.textContent).join('|')!=='분석 리포트|확률 예측' ||
               selected()!=='분석 리포트' || q('.forecast-reports') || caseQueries.length || directoryRequests)throw Error('report list default');
            reportTabs()[1].click();
            await wait(()=>q('.forecast-reports a[href="#/research/201"]')?.textContent.includes('39.0%'));
            if(document.querySelectorAll('.forecast-reports a').length!==2 || q('.forecast-reports').textContent.includes('더 보기'))throw Error('ticker directory');
            if(selected()!=='확률 예측' || q('.report-directory'))throw Error('mixed report types');
            const ledger=q('.forecast-reports'), estimate=q('.forecast-reports .figure strong');
            if(getComputedStyle(ledger).backgroundColor!=='rgb(252, 253, 251)' ||
              getComputedStyle(estimate).color!=='rgb(130, 66, 111)') throw Error('forecast ledger theme');
            q('.forecast-reports button[aria-label="확률 예측 새로고침"]').click();
            await wait(()=>directoryRequests===2 && !q('.forecast-reports .refresh').disabled);
            q('.forecast-reports a').click();
            await wait(()=>q('.evidence h2')?.textContent.includes('엔비디아') && q('#forecast-round')?.textContent.includes('201회차'));
            q('#forecast-round').click();
            await wait(()=>document.querySelectorAll('[role=option]').length===201);
            const oldest=[...document.querySelectorAll('[role=option]')].at(-1);
            if(oldest.textContent.trim()!=='1회차 · 2026-11-24' || !roundQueries.some(p=>p.before_id==='2' && p.ticker==='NVDA'))throw Error('full ticker-specific history');
            oldest.click();
            await wait(()=>location.hash==='#/research/1' && q('.headline strong')?.textContent.includes('28.0%') && q('#forecast-round')?.textContent.includes('1회차'));
            history.back();
            await wait(()=>location.hash==='#/research/201' && q('#forecast-round')?.textContent.includes('201회차') && q('.headline strong')?.textContent.includes('39.0%'));
            history.back();
            await wait(()=>selected()==='확률 예측' && q('.forecast-reports a'));
            if(directoryRequests!==2 || roundQueries.length!==2)throw Error('fresh ticker directory or prior rounds refetched');
            q('.forecast-reports .refresh').click();
            await wait(()=>q('.forecast-reports a[href="#/research/203"]'));
            q('.forecast-reports a').click();
            await wait(()=>q('#forecast-round')?.textContent.includes('202회차 · 2026-11-25'));
            if(roundQueries.length!==4 || roundQueries.at(-1)?.before_id!=='3')throw Error('new publication did not revalidate ticker history once');
            history.back();
            await wait(()=>selected()==='확률 예측' && q('.forecast-reports a'));
            reportTabs()[0].click();
            await wait(()=>q('.round-picker button'));
            const expectedControlHeight = matchMedia('(max-width: 767px)').matches ? 44 : 42;
            for (const selector of ['.desk-search','.report-kind button','.round-picker button']) {
              const element=q(selector), box=element.getBoundingClientRect();
              if (Math.abs(box.height-expectedControlHeight)>1 || parseFloat(getComputedStyle(element).borderRadius)<12)
                throw Error(selector+' control '+box.height+' / '+getComputedStyle(element).borderRadius);
            }
            q('.round-picker button').click();
            await wait(()=>q('.rounds a[href$="report=8"]'));
            q('.rounds a[href$="report=8"]').click();
            await wait(()=>q('#cycle-select') && q('.archive') && resolveFirst);
            q('#cycle-select').click(); await wait(()=>q('[role=option][aria-selected=false]'));
            q('[role=option][aria-selected=false]').click(); await wait(()=>q('.archive')?.innerText.includes('회차 자료 7'));
            const [emptyArchive,newsArchive]=document.querySelectorAll('.archive .source');
            const delivered=q('.archive .news-input');
            if(!delivered?.innerText.includes('입력 기준') || !delivered.innerText.includes('인용된 제목') ||
               !delivered.innerText.includes('최종 판단 인용 1건') || delivered.innerText.includes('입력에만 보관된 제목'))
              throw Error('saved references and citations');
            delivered.querySelector('button').click();
            await wait(()=>delivered.innerText.includes('입력에만 보관된 제목'));
            if(delivered.querySelectorAll('article').length!==42 || !delivered.querySelector('article').innerText.includes('N42') ||
               !delivered.querySelector('article').innerText.includes('뉴스 분석가 인용'))
              throw Error('all delivered headlines');
            delivered.querySelector('button').click();
            const expand=newsArchive.querySelector('h4 > button[aria-expanded="false"]');
            if(!emptyArchive.querySelector('h4')?.textContent.includes('last30days') ||
               !emptyArchive.textContent.includes('0건') || emptyArchive.querySelector('button') ||
               !expand?.textContent.includes('뉴스') || !expand.textContent.includes('2건') ||
               newsArchive.querySelectorAll('button').length!==1 || newsArchive.querySelectorAll('.item').length!==1)throw Error('archive group preview');
            if(!(q('.desk-conclusion').compareDocumentPosition(q('.archive')) & Node.DOCUMENT_POSITION_FOLLOWING))throw Error('conclusion not first');
            expand.focus();
            if(document.activeElement!==expand || expand.tabIndex!==0 || expand.getBoundingClientRect().height<44)throw Error('archive header hit target or focus');
            expand.click(); await wait(()=>newsArchive.querySelectorAll('.item').length===2);
            const extra=newsArchive.querySelector('a[href="https://example.org/more/7"]');
            if(expand.getAttribute('aria-expanded')!=='true' || !extra?.textContent.includes('추가 자료 7') ||
               extra.target!=='_blank' || !extra.relList.contains('noopener'))throw Error('expanded archive links');
            expand.click(); await wait(()=>newsArchive.querySelectorAll('.item').length===1);
            if(expand.getAttribute('aria-expanded')!=='false' || !newsArchive.querySelector('.item').textContent.includes('회차 자료 7'))throw Error('collapse keeps archive preview');
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

        class Handler(BundleHandler):
            def do_GET(self):
                if self.path != DIST_BASE:
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
                        f"http://127.0.0.1:{server.server_port}{DIST_BASE}",
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
