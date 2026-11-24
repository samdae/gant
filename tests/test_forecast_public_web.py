"""Render the public assets with Chromium and exercise public routes without a service."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


WEB = Path(__file__).resolve().parents[1] / "packages/tradingagents/forecast_lab/public_web"
CHROME = next((exe for exe in (
    os.environ.get("CHROME_BIN"), shutil.which("chromium"), shutil.which("google-chrome"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
) if exe and Path(exe).is_file()), None)


@unittest.skipUnless(CHROME, "A Chromium browser is required")
class PublicWebTests(unittest.TestCase):
    def test_lists_details_scores_and_empty_cohort(self):
        example = dict(id=7, ticker="SPY", name="미국 대형주 지수 연구용 종목", market="us",
                       data_session="2026-10-22", status="awaiting")
        report = dict(id=9, ticker="SPY", name=example["name"], market="us", decision="BUY",
                      summary="**공개 요약**", sections=[{"title": "분석 근거", "text": "지표 관측"}])
        responses = {"overview": {"cases": [example], "comparisons": [
            dict(control="single", treated="memory", n=3, improvement=-0.08, control_brier=.17, treated_brier=.25)
        ]}, "cases/7": {**example, "forecasts": [{"method": "single", "probability": .2}]},
            "reports": {"reports": [report, {**report, "id": 10, "name": "비트코인", "ticker": "BTC-USD", "market": "crypto"}]}, "reports/9": report}
        checks = """
        (async () => {
          const issues=[];
          const check=(ok, label)=>{if(!ok)issues.push(label)};
          async function page(hash) {location.hash=hash;await render();await new Promise(r=>setTimeout(r,20));}
          try {
            await page("#/research");
            check(document.querySelector(".identity strong")?.innerText===data.overview.cases[0].name, "company first");
            check([...document.querySelector("select").options].map(x=>x.value).join(",")===",us","available forecast markets");
            check(document.documentElement.scrollWidth<=innerWidth,"list overflow");
            const search=document.querySelector("input");search.value="없는종목";search.oninput();
            check(main.innerText.includes("조건에 맞는 종목이 없습니다"),"search");
            await page("#/research/7");check(main.innerText.includes("20.0%") && main.innerText.includes("만기 결과"),"forecast");
            await page("#/reports");check(document.querySelector(".row").hash==="#/reports/9","report link");
            const filter=document.querySelector("select");filter.value="crypto";filter.onchange();
            check(filter.selectedOptions[0].text==="디지털자산" && document.querySelectorAll(".row").length===1 &&
              document.querySelector(".row").innerText.includes("비트코인") && document.querySelector(".row").innerText.includes("디지털자산"),"crypto report");
            await page("#/reports/SPY");check(main.innerText.includes("분석 근거") && !main.innerText.includes("**"),"legacy detail");
            await page("#/results");check(main.innerText.includes("3쌍") && main.innerText.includes("-0.080 악화"),"matched");
            document.querySelector(".skip").click();
            check(location.hash==="#/results" && document.activeElement===main,"skip link retained route");
            data.overview.comparisons=[];await render();check(main.innerText.includes("비교 표본이 아직 없습니다"),"empty");
            check(document.documentElement.scrollWidth<=innerWidth,"result overflow");
            check(document.querySelector(".admin").href==="https://lab.daehun.app/","admin domain");
          } catch(e) {issues.push(String(e));}
          const output=document.createElement("output");output.id="test-result";output.textContent=issues.join("/")||"passed";
          document.body.replaceChildren(output);
        })();
        """
        html = (WEB / "index.html").read_text(encoding="utf-8-sig")
        html = html.replace('<link rel="stylesheet" href="/public.css" />', "<style>" +
                            (WEB / "public.css").read_text(encoding="utf-8-sig") + "</style>")
        html = html.replace('<script defer src="/public.js"></script>', "")
        html = html.replace("</body>", "<script>const data=" + json.dumps(responses) +
                            ";window.fetch=async p=>({ok:true,json:async()=>data[p.replace('/public-api/','')]});</script>"
                            + "<script>" + (WEB / "public.js").read_text(encoding="utf-8-sig") + "</script>"
                            + "<script>" + checks + "</script></body>")
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "public.html"
            fixture.write_text(html, encoding="utf8")
            for width in (393, 1440):
                with self.subTest(width=width):
                    dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                        "--virtual-time-budget=2500", f"--window-size={width},900",
                        f"--user-data-dir={directory}/profile-{width}", "--dump-dom", fixture.as_uri()],
                        capture_output=True, encoding="utf8", errors="replace", timeout=30, check=True).stdout
                    self.assertIn('<output id="test-result">passed</output>', dom[-500:])
