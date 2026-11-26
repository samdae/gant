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


def bundle_base():
    shell = DIST / "index.html"
    if shell.is_file() and 'src="/v4/assets/' in shell.read_text(encoding="utf8"):
        return "/v4/"
    return "/"


DIST_BASE = bundle_base()


class BundleHandler(SimpleHTTPRequestHandler):
    """Serve the same static bundle at its production mount point."""
    def translate_path(self, path):
        if DIST_BASE != "/" and path.startswith(DIST_BASE):
            path = "/" + path[len(DIST_BASE):]
        return super().translate_path(path)


@unittest.skipUnless(os.environ.get("FORECAST_PUBLIC_UI_DIST") and CHROME and (DIST / "index.html").exists(), "requires Chromium and a built Forecast Lab bundle")
class IntegratedPublicViewerTests(unittest.TestCase):
    def test_anonymous_reads_with_stale_admin_state(self):
        forbidden = []
        checks = """
        (async()=>{
          const errors=[];
          async function wait(test) {for(let i=0;i<100;i++){if(test())return;await new Promise(r=>setTimeout(r,25));}throw Error(location.hash+' '+test);}
          async function visit(hash,test){location.hash=hash;await wait(test);}
          function check(ok,label){if(!ok)errors.push(label);}
          function material(token) {
            const node=document.createElement('span');
            node.style.background='var('+token+')';
            document.body.append(node);
            const css=getComputedStyle(node);
            const value=[css.backgroundColor,css.backgroundImage];
            node.remove();
            return value;
          }
          try {
            await wait(()=>document.querySelector('.workspace'));
            await wait(()=>document.querySelector('#page-reports'));
            check(location.hash==='#/reports' && document.querySelector('#page-reports h2')?.textContent==='리포트', 'report home');
            check([...document.querySelectorAll('.rail-brand a,.mobile-brand')].every(link=>link.hash==='#/dashboard' && link.getAttribute('aria-label')==='GANT 대시보드'), 'brand opens dashboard');
            const search=document.querySelector('.desk-search input');
            search.focus();
            check(getComputedStyle(search).outlineStyle==='none' && getComputedStyle(search.closest('label')).outlineWidth==='2px', 'single search focus ring');
            await wait(()=>document.querySelector('.viewport-progress.visible'));
            const indicator=document.querySelector('.viewport-progress');
            const box=indicator.getBoundingClientRect();
            check(Math.abs(box.x+box.width/2-innerWidth/2)<1 && Math.abs(box.y+box.height/2-innerHeight/2)<1 &&
              !indicator.contains(document.elementFromPoint(innerWidth/2,innerHeight/2)), 'centered click-through progress');
            if(matchMedia('(max-width:900px)').matches){
              const menu=document.querySelector('.phone-tabs button');
              const drawer=document.getElementById('workspace-drawer');
              menu.click();
              await wait(()=>drawer.open && !indicator.classList.contains('visible'));
              drawer.querySelector('button').click();
              check(drawer.dataset.motion==='closing' || matchMedia('(prefers-reduced-motion: reduce)').matches, 'drawer dismiss transition');
              await wait(()=>!drawer.open);
              await wait(()=>indicator.classList.contains('visible'));
            }
            window.releaseDirectory();
            await wait(()=>!indicator.classList.contains('visible'));
            check(document.querySelector('.public-lamp') && getComputedStyle(document.querySelector('.access')).display!=='none' &&
              document.querySelector('.access').textContent.trim()==='공개 열람', 'visible public access status');
            check(document.querySelector('.phone-tabs a[href="#/research"]'), 'research tab retained');
            check(!document.querySelector('.desktop-rail a[href="#/auth"]'),'admin menu');
            await visit('#/research/29',()=>document.querySelector('.evidence h2')?.textContent.includes('삼성전자'));
            check(document.querySelector('.headline').textContent.includes('61.0%'),'published probability');
            await wait(()=>document.querySelectorAll('.register a').length===3);
            const picker=document.querySelector('.research-desk dialog');
            check(!picker.open,'compact picker initially closed');
            document.querySelector('.choose').click();
            check(picker.open && getComputedStyle(picker).backgroundColor===material('--fl-surface')[0] &&
              getComputedStyle(picker).colorScheme==='light','light reading surface in picker');
            const marketPicker=picker.querySelector('[role="combobox"]');
            const press=async (control,key)=>{
              control.dispatchEvent(new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));
              await Promise.resolve();
            };
            marketPicker.focus();
            await press(marketPicker,'Enter');
            const marketList=picker.querySelector('[role="listbox"]');
            check(marketList?.matches(':popover-open') && marketList.querySelector('[aria-selected="true"]') &&
              getComputedStyle(marketList).opacity==='1' &&
              getComputedStyle(marketList).backgroundColor===material('--fl-glass-raised')[0] &&
              getComputedStyle(marketList).backgroundImage===material('--fl-glass-raised')[1], 'raised market selection inside dialog');
            await press(marketPicker,'End');
            check(marketPicker.getAttribute('aria-activedescendant')===marketList.lastElementChild.id,'End focuses last market');
            await press(marketPicker,'Escape');
            check(picker.open && marketPicker.getAttribute('aria-expanded')==='false' && document.activeElement===marketPicker, 'Escape dismisses list and retains dialog focus');
            const [first,partial,unissued]=document.querySelectorAll('.register a');
            check(partial.textContent.includes('일부 방법 발행') && !partial.textContent.includes('발행 대기') &&
              unissued.textContent.includes('발행 대기') && first.textContent.includes('채점 완료'),'partial vs unissued');
            const pickerClosed=new Promise(resolve=>picker.addEventListener('close',resolve,{once:true}));
            picker.querySelector('.close').click();await pickerClosed;
            check(!picker.open && document.activeElement.matches('.choose'),'picker closes and restores focus');
            const slider=document.querySelector('.chart .pointer');
            slider.value='0';slider.dispatchEvent(new Event('input',{bubbles:true}));await Promise.resolve();
            check(slider.getAttribute('aria-valuetext').includes('2026-10-28') && slider.getAttribute('aria-valuetext').includes('74,000원'), 'interactive dated close');
            const chart=document.querySelector('.chart'), candle=[...chart.querySelectorAll('.type button')].find(x=>x.textContent.includes('캔들'));
            candle.click();await Promise.resolve();
            check(chart.querySelectorAll('g.candle').length===1 && chart.querySelectorAll('.volume-bar').length===1 &&
              chart.querySelector('.bar-values').textContent.includes('12,345주'), 'frozen OHLC and actual volume only');
            const priceColor = getComputedStyle(chart.querySelector('.candle.rising rect')).fill;
            const modelColor = getComputedStyle(document.querySelector('.track i')).backgroundColor;
            check(modelColor===material('--fl-forecast')[0] && priceColor===material('--fl-chart-line')[0] &&
              priceColor!==modelColor, 'distinct price and model colors');
            check(document.querySelector('.range-summary')?.textContent.includes('50.0%–61.0%') && document.querySelector('.range-summary')?.textContent.includes('11.0%p'), 'published model range');
            check(document.querySelector('.comparison').textContent.includes('61.0%') && document.querySelector('.axis').textContent.includes('50%'), 'common probability axis');
            [...document.querySelectorAll('.compare-row')].find(el=>el.textContent.includes('역할 토론')).click();
            check(document.querySelector('.model[open] > summary')?.textContent.includes('역할 토론') && document.activeElement===document.querySelector('.model[open] > summary'),'model-specific judgment focus');
            check(document.querySelector('.condition').textContent.includes('75,000원') &&
              document.querySelector('.condition').textContent.includes('충족'),'frozen condition');
            check(document.querySelector('.sources').textContent.includes('당시 확인된 공시') &&
              document.querySelector('.sources').textContent.includes('시간 미상') && document.querySelector('.feed.lead a').textContent.includes('커뮤니티 기록'),'archived news precision');
            check(document.querySelector('.chart svg').getAttribute('aria-label').includes('2026-10-28'), 'frozen price chart');
            check([...document.querySelectorAll('.model summary')].some(s=>s.textContent.includes('역할 토론')), 'research methods');
            const debate=[...document.querySelectorAll('.model')].find(d=>d.querySelector('summary').textContent.includes('역할 토론'));
            debate.open=true;debate.querySelector('.turn').open=true;
            check(debate.querySelector('.turn .narrative strong')?.textContent.includes('근거') && !debate.querySelector('img'), 'sanitized transcript');
            check(document.querySelector('.sources .feed').textContent.includes('동결 목록에 포함') &&
              document.querySelectorAll('.sources a[href="https://example.org/post"]').length===1 &&
              [...document.querySelectorAll('.sources .feed')].some(el=>el.textContent.includes('수집 경로 미확인') && el.textContent.includes('수집 단계 미상')),
              'mixed sources attributed and deduplicated');
            const [community,rss,unmatched]=document.querySelectorAll('.sources .feed');
            const header=feed=>feed.querySelector('h4 > button[aria-expanded]');
            const articles=feed=>feed.querySelectorAll('.news').length;
            check(articles(community)===1 && articles(rss)===1 && articles(unmatched)===1 &&
              !header(unmatched) && unmatched.querySelector('h4').textContent.includes('1건'), 'single source is a static preview');
            const communityToggle=header(community), rssToggle=header(rss);
            check(communityToggle.textContent.includes('2건') && rssToggle.textContent.includes('2건') &&
              community.querySelectorAll('button').length===1 && rss.querySelectorAll('button').length===1 &&
              communityToggle.getAttribute('aria-controls')!==rssToggle.getAttribute('aria-controls'), 'independent named source lists');
            communityToggle.focus();communityToggle.click();await wait(()=>articles(community)===2);
            check(communityToggle.getAttribute('aria-expanded')==='true','community header announces expansion');
            check(document.activeElement===communityToggle,'source header retains keyboard focus');
            check(articles(rss)===1 && rssToggle.getAttribute('aria-expanded')==='false', 'RSS preview stays closed');
            rssToggle.click();await wait(()=>articles(rss)===2);
            communityToggle.click();await wait(()=>articles(community)===1);
            check(articles(rss)===2 && rss.querySelector('a[href="https://example.org/update"]') &&
              community.querySelector('a[href="https://example.org/post"]'), 'collapse keeps first source and sibling state');
            check(document.documentElement.scrollWidth<=innerWidth,'research overflow');
            await visit('#/research/28',()=>document.querySelector('.compare-row b')?.textContent==='0.0%');
            check(document.querySelectorAll('.sources .feed h4 > button[aria-expanded="false"]').length===2 &&
              !document.querySelector('.sources a[href="https://example.org/update"]'), 'a new case starts with source previews');
            check(!document.querySelector('.range-summary'),'single probability has no range');
            await visit('#/research/27',()=>document.querySelector('.sources')?.textContent.includes('당시 수집 기록이 없습니다.'));
            check(!document.querySelector('.range-summary') && !document.querySelector('.news') && document.querySelector('.chart .type button:disabled') && document.querySelector('.chart').textContent.includes('종가'), 'genuine empty source and chart');
            await visit('#/observe',()=>[...document.querySelectorAll('h2')].some(el=>el.textContent.includes('관측 현황')));
            await visit('#/results',()=>[...document.querySelectorAll('h2')].some(el=>el.textContent.includes('예측 성과')));
            await visit('#/schedules',()=>document.querySelector('main a[href="#/schedules/spy"]'));
            check(!document.querySelector('#addScheduleBtn, .op-cancel'),'schedule actions');
            await visit('#/schedules/SPY',()=>document.querySelector('main')?.innerText.includes('세부 실행 로그'));
            const round=document.getElementById('schedule-round');
            round.focus();
            await press(round,'ArrowDown');
            await press(round,'End');
            await press(round,'Enter');
            check(round.textContent.includes('2회') && round.getAttribute('aria-expanded')==='false','round selection commits');
            await visit('#/live',()=>document.querySelector('main')?.innerText.includes('현재 실행 종목과 대기열'));
            await visit('#/retrospective',()=>document.querySelector('.review-empty'));
            check(!document.querySelector('.review-empty button'),'retrospective actions');
            await visit('#/portfolio?setup=1',()=>document.body.innerText.includes('모의 계좌 미개설'));
            check(!document.querySelector('dialog[open], .modal-overlay'),'account setup');
            await visit('#/reports/7',()=>document.querySelector('.report-meta'));
            check(document.querySelector('main h2').textContent.includes('SPY'),'legacy numeric report');
            await visit('#/auth',()=>location.hash==='#/reports');
            check(!document.querySelector('#tokenInput'),'auth');
            check(!window.socketCalls,'websocket');
            check(localStorage.getItem('gant_admin_token')==='stale-test-only','stale token modified');
            check(document.documentElement.scrollWidth<=innerWidth,'overflow');
          }catch(e){errors.push(String(e));}
          const o=document.createElement('output');o.id='result';o.textContent=errors.join('/')||'passed';document.body.replaceChildren(o);
        })()
        """
        class Handler(BundleHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                path = urlsplit(self.path).path
                if self.headers.get("Authorization") or "/events" in path or "retry-candidates" in path or path.startswith("/ws/"):
                    forbidden.append(path)
                if path == DIST_BASE:
                    html = (DIST / "index.html").read_text(encoding="utf8").replace("<head>", '<head><meta name="forecast-console-access" content="public-readonly"><script>localStorage.setItem("gant_admin_token","stale-test-only");window.socketCalls=0;window.WebSocket=class{constructor(){window.socketCalls++}}</script>')
                    gate = """<script>
                    const directoryGate=new Promise(done=>window.releaseDirectory=done);
                    const fetchWithoutGate=window.fetch;
                    window.fetch=async (...args)=>{
                      if(String(args[0]?.url||args[0]).includes('/reports/tickers')) await directoryGate;
                      return fetchWithoutGate(...args);
                    };
                    </script>"""
                    raw = html.replace("<head>", "<head>"+gate).replace("</body>", "<script>"+checks+"</script></body>").encode()
                    content = "text/html; charset=utf-8"
                elif path.startswith("/api/cases"):
                    row=dict(id=29,ticker="005930.KS",market="kr",data_session="2026-11-02",status="matured",forecast_probabilities={"single":0.61})
                    detail={**row,"arms":[{"method":"single","status":"published","probability":.61},{"method":"debate","status":"published","probability":.5,"rationale":"**참고**","audit":{"debate":[{"role":"create_bull_researcher","output":"**근거**"}]}}],
                            "outcome":{"status":"scored","actual":1},"snapshot":{"currency":"KRW","classification":{"asset_class":"equity"},"bars":[{"date":"2026-10-28","open":73900,"high":74200,"low":73700,"close":74000,"volume":12345},{"date":"2026-11-02","close":74700}]},
                            "hypothesis":{"currency":"KRW","conditions":[{"id":"breakout","metric":"exit_close","operator":"gt","threshold":75000,"status":"met","observed_value":76000}]},
                            "last30days":{"status":"available","source":"last30days agent export","items":[{"title":"커뮤니티 기록","url":"https://example.org/post","publisher":"커뮤니티"}]},
                            "issues":{"status":"available","items":[{"title":"당시 확인된 공시","publisher":"공시 자료","source":"Google News RSS","url":"https://example.org/release","published_precision":"day","published_day":"2026-11-01"},{"title":"커뮤니티 기록","publisher":"커뮤니티","source":"last30days agent export","url":"https://example.org/post"},{"title":"수집 단계 미상","url":"https://example.org/old"}]}}
                    detail["last30days"]["items"].append({"title":"후속 토론","url":"https://example.org/discussion","publisher":"커뮤니티"})
                    detail["issues"]["items"].append({"title":"추가 공시","url":"https://example.org/update","source":"Google News RSS","publisher":"공시 자료"})
                    partial={**row,"id":28,"status":"pending","forecast_probabilities":{"single":0.0}}
                    unissued={**row,"id":27,"status":"pending","forecast_probabilities":{}}
                    if path == "/api/cases":
                        payload = [row, partial, unissued]
                    elif path.endswith("/27"):
                        payload = {**unissued, "arms": [], "snapshot": {}}
                    elif path.endswith("/28"):
                        payload = {**detail, **partial, "arms": [
                            {"method": "single", "status": "published", "probability": 0.0}
                        ]}
                    else:
                        payload = detail
                    raw = json.dumps(payload).encode()
                    content="application/json"
                elif path.startswith(("/workspace-api/", "/public-api/")):
                    data = {"/workspace-api/schedules":[{"ticker":"SPY","interval_days":1}],
                            "/workspace-api/schedules/SPY/cycles":[{"id":2,"scheduled_cycle":3,"status":"done","created_at":"2026-11-01T00:00:00Z"},{"id":1,"scheduled_cycle":2,"status":"done","created_at":"2026-10-31T00:00:00Z"}],
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
                for width in [360,393,1440]:
                    with self.subTest(width=width):
                        url=f"http://127.0.0.1:{server.server_port}{DIST_BASE}"
                        dom=subprocess.run([CHROME,"--headless=new","--disable-gpu","--no-first-run","--no-proxy-server",
                            "--virtual-time-budget=12000",f"--window-size={width},900",f"--user-data-dir={root}/{width}",
                            "--dump-dom",url],capture_output=True,encoding="utf8",errors="replace",timeout=35,check=True).stdout
                        self.assertIn('<output id="result">passed</output>',dom[-500:])
            self.assertEqual(forbidden,[])
        finally:
            server.shutdown();server.server_close()
