import assert from "node:assert/strict";
import { once } from "node:events";
import { test } from "node:test";
import { createPulseReader } from "../../../scripts/v4-report-pulse.mjs";
import { previewServer } from "../../../scripts/v4-preview.mjs";

const recent = "2026-11-26T09:02:33.000123+09:00";
const older = "2026-11-25T09:00:41+09:00";

function round(ticker, id, decision, created_at, cycle) {
  return { ticker, id, scheduled_cycle: cycle, created_at, stored_decision_position: decision,
    decision_position: "HOLD", portfolio_action: "BUY", final_trade_decision: "**핵심 근거:** EPS $3.23 기준으로 40.9배입니다. 다만 마진은 개선됐습니다.\n\n**실행 계획**\n후속 절차" };
}

function summary(ticker, stored_decision_position, report_count = 2) {
  return { ticker, latest_at: recent, latest_cycle: 3, report_count, stored_decision_position };
}

function sources(directory, history) {
  return async (path) => {
    if (path === "/workspace-api/reports/tickers") return directory;
    const query = new URL(path, "http://example.test").searchParams;
    assert.equal(query.get("limit"), "2");
    return history[query.get("ticker")];
  };
}

test("every comparison has the two actual published report IDs; unrecorded decisions stay unknown", async () => {
  const list = [summary("WMT", "SELL", 3), summary("NVDA", null), summary("KO", "HOLD", 1), summary("DLR", "HOLD")];
  const read = createPulseReader({read: sources(list, {
    WMT: [round("WMT", 1300, "SELL", recent, 3), round("WMT", 1276, "HOLD", older, 1)],
    NVDA: [round("NVDA", 1299, null, recent, 3), round("NVDA", 1275, "SELL", older, 2)],
    KO: [round("KO", 1298, "HOLD", recent, 3)],
    DLR: [round("DLR", 1297, "HOLD", recent, 3), round("DLR", 1277, "HOLD", older, 2)],
  })});
  const {rows} = await read();
  assert.deepEqual(rows.map(r=>r.status), ["changed", "unknown", "first", "unchanged"]);
  assert.deepEqual(rows[0].current, { id: 1300, cycle: 3, at: recent, decision: "SELL" });
  assert.equal(rows[0].previous.id, 1276);
  assert.equal(rows[0].previous.cycle, 1); // An unissued cycle is never a prior published report.
  assert.equal(rows[0].reason, "EPS $3.23 기준으로 40.9배입니다. 다만 마진은 개선됐습니다.");
  assert.equal(rows[1].current.decision, null);
  assert.equal(rows[2].previous, null);
});

test("a truncated, out-of-order or mismatched pair cannot become a false change", async () => {
  const cases = [
    [round("NVDA", 9, "BUY", recent, 3), round("WMT", 8, "SELL", older, 2)],
    [round("WMT", 9, "BUY", recent, 3), round("NVDA", 8, "SELL", older, 2)],
    [round("WMT", 9, "BUY", recent, 3), round("WMT", 9, "SELL", recent, 2)],
    [round("WMT", 9, "BUY", recent, 3)],
    [round("WMT", 9, "SELL", recent, 3), round("WMT", 8, "BUY", older, 2)],
    [round("WMT", 9, "BUY", recent.replace("000123","000122"), 3), round("WMT", 8, "SELL", older, 2)],
  ];
  for (const pair of cases) {
    const read = createPulseReader({ read: sources([summary("WMT", "BUY")], {WMT: pair}) });
    const [row] = (await read()).rows;
    assert.equal(row.status, "unavailable");
    assert.equal(row.current, null);
    assert.equal(row.previous, null);
    assert.equal(row.reason, null);
  }
});

test("reason extracts preserve an unlabelled explanation and leave absent rationale empty", async () => {
  const full = round("KO", 1292, "HOLD", recent, 3);
  const directory = [summary("KO", "HOLD", 1)];
  for (const [raw, expected] of [
    ["관망을 유지합니다. 영업이익 12.1% 증가, 마진 개선은 보유 근거입니다. 다만 판매량 기여는 확인되지 않았습니다.",
      "영업이익 12.1% 증가, 마진 개선은 보유 근거입니다. 다만 판매량 기여는 확인되지 않았습니다."],
    ["**최종 판단:** 관망\n\n**실행 목표:** 보유", null],
    ['{"reason":"공개 마크다운 아님"}', null],
  ]) {
    const read = createPulseReader({ read: sources(directory, { KO: [{ ...full, final_trade_decision: raw }] }) });
    assert.equal((await read()).rows[0].reason, expected);
  }
});

test("a failed directory is retried and cannot direct requests outside the public ticker history", async () => {
  let now = Date.parse(recent);
  let calls = 0;
  let directory = [summary("../api/admin", "HOLD")];
  const read = createPulseReader({ now: () => now, read: async path => {
    calls++;
    assert.equal(path, "/workspace-api/reports/tickers");
    return directory;
  } });
  await assert.rejects(read());
  await assert.rejects(read());
  assert.equal(calls, 1);
  directory = [];
  now += 16_000;
  assert.deepEqual((await read()).rows, []);
  assert.equal(calls, 2);
});

test("snapshot refresh coalesces demand, reads only changed ticker versions and retries a partial failure", async () => {
  let clock = Date.parse(recent), dirs = 0, requests = [];
  const directory = [summary("WMT", "BUY"), summary("NVDA", "HOLD")];
  const history = {
    WMT: [round("WMT", 9, "BUY", recent, 3), round("WMT", 7, "HOLD", older, 2)],
    NVDA: [round("NVDA", 8, "HOLD", recent, 3), round("NVDA", 6, "HOLD", older, 2)],
  };
  let fail = true;
  const source = sources(directory, history);
  const read = createPulseReader({ now: () => clock, read: async(path) => {
    if (path.endsWith("/tickers")) dirs++;
    else {
      const ticker = new URL(path, "http://example.test").searchParams.get("ticker");
      requests.push(ticker);
      if (ticker === "WMT" && fail) throw Error("Temporary failure");
    }
    return source(path);
  }});
  const first = await Promise.all([read(),read(),read()]);
  assert.equal(dirs, 1);
  assert.deepEqual(requests.sort(), ["NVDA","WMT"]);
  assert.equal(first[0].rows[0].status, "unavailable");
  fail = false;
  clock += 46_000;
  const next = await read();
  assert.equal(dirs, 2);
  assert.equal(requests.length, 3);
  assert.equal(requests.at(-1), "WMT");
  assert.equal(next.rows[0].status, "changed");
  clock += 301_000;
  await read();
  assert.equal(dirs, 3);
  assert.equal(requests.length, 3); // rechecked the short directory only
  directory[1] = {...directory[1], report_count: 3, latest_at: "2026-11-27T09:00:12+09:00"};
  history.NVDA = [round("NVDA", 11, "HOLD", directory[1].latest_at, 4), history.NVDA[0]];
  clock += 301_000;
  const update = await read();
  assert.equal(requests.length, 4);
  assert.equal(update.rows[1].current.id, 11);
  assert.equal(update.rows[1].previous.id, 8);
});

test("public JSON adapter is a single scoped read with transient failures handled distinctly", async t => {
  let healthy = false;
  const pulse = {as_of:recent,rows:[]};
  const server = previewServer(".", async () => {if (!healthy) throw Error("failure"); return pulse;});
  server.listen(0,"127.0.0.1");
  await once(server,"listening");
  t.after(() => server.close());
  const origin = "http://127.0.0.1:"+server.address().port;
  const path = "/v4/data/report-pulse";
  assert.equal((await fetch(origin+path)).status,503);
  healthy = true;
  const verified = await fetch(origin+path);
  assert.deepEqual(await verified.json(), pulse);
  assert.match(verified.headers.get("cache-control"), /max-age=60/);
  assert.equal(await (await fetch(origin+path,{method:"HEAD"})).text(),"");
  assert.equal((await fetch(origin+path+"?url=https://example.com")).status,400);
  assert.equal((await fetch(origin+path,{method:"POST"})).status,405);
  assert.equal((await fetch(origin+"/v4/data/other")).status,404);
});
