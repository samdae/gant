"use strict";
const $ = (id) => document.getElementById(id);
const names = {
  baseline: "빈도 기준선",
  single: "단일 모델",
  debate: "8개 역할 토론",
  memory: "기억을 제공한 단일 모델",
};
const labels = {
  pending: "발행 대기",
  awaiting: "만기 대기",
  matured: "채점 완료",
  excluded: "평가 제외",
  unpublished: "미발행",
  failed: "실패",
  published: "발행",
  skipped: "건너뜀",
  scored: "채점 완료",
};
let selected = null;
let activeRequest = 0;
let refreshSerial = 0;
let filters = new URLSearchParams();
let cursors = [null];
let lastId = null;
let listKey = "";
let detailKey = "";
const pageSize = 20;
const el = (tag, value, cls) => {
  const node = document.createElement(tag);
  if (value != null) node.textContent = String(value);
  if (cls) node.className = cls;
  return node;
};
const msg = (a, b) => a + " · " + (b ?? "미확인");
const num = (value) => (value == null ? "—" : Number(value).toFixed(3));
const versionLabel = (v) =>
  ({
    "direction-5s-v1": "초기 시범",
    "direction-5s-v2": "분할·배당 확인",
    "laplace-5s-v1": "과거 5거래일 빈도",
    "frozen-probability-v1": "동결 근거 단일 예측",
    "original-eight-nodes-1round-risk-forecast-v1": "8개 역할 토론 · 1회",
  })[v] ?? "기타 실험 방식";
const route = new URLSearchParams(location.search);
if (route.get("embedded") === "1")
  document.documentElement.classList.add("embedded");
const pct = (value) =>
  value == null ? "—" : (Number(value) * 100).toFixed(1) + "%";
const kstFormat = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
function kst(value) {
  if (!value) return "—";
  if (!/(Z|[+-]\d{2}:\d{2})$/i.test(value)) return value;
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? kstFormat.format(date) + " KST"
    : "—";
}
const roles = {
  create_bull_researcher: "강세 분석가",
  create_bear_researcher: "약세 분석가",
  create_research_manager: "투자 토론 심판",
  create_trader: "트레이더",
  create_aggressive_debator: "공격적 위험 분석가",
  create_conservative_debator: "보수적 위험 분석가",
  create_neutral_debator: "중립 위험 분석가",
  create_risk_manager: "최종 위험 심판",
};
const numeric = (v) => typeof v === "number" && Number.isFinite(v);
const amount = (v, currency) =>
  numeric(v)
    ? new Intl.NumberFormat("ko-KR", {
        style: "currency",
        currency: currency === "KRW" ? "KRW" : "USD",
        maximumFractionDigits: currency === "KRW" ? 0 : 2,
      }).format(v)
    : "—";
const integer = (v) => (numeric(v) ? v.toLocaleString("ko-KR") : "—");
const upLabel = (y) =>
  y === 1 ? "상승" : y === 0 ? "보합 또는 하락" : "관측 대기";
const modelLabel = (v) =>
  v === "deterministic" ? "통계 기준선" : v || "모델 미확인";
function why(value) {
  const s = String(value ?? "");
  const reasons = [
    [
      /no eligible matured memory/i,
      "이 시점에 사용할 수 있는 채점 완료 사례가 없습니다.",
    ],
    [
      /entry session.*open|window closed|deadline/i,
      "다음 거래일이 개장해 예측 발행을 마감했습니다.",
    ],
    [
      /21-session|corporate.action|incomplete, split/i,
      "최근 거래일의 연속 시세 또는 배당·분할 영향을 확인할 수 없습니다.",
    ],
    [/dividend/i, "배당 전후의 가격 조정 기준을 확인할 수 없습니다."],
    [/split/i, "평가 기간에 주식 분할이 있었습니다."],
    [
      /incomplete|missing|no verified|price window/i,
      "평가에 필요한 거래일 시세가 충분하지 않습니다.",
    ],
    [/calendar/i, "거래소 일정이 변경됐습니다."],
    [/timeout|time budget/i, "정해진 시간 안에 자료나 응답을 받지 못했습니다."],
    [/provider|rate.limit/i, "시세 제공처의 응답을 확인하지 못했습니다."],
  ];
  return (
    reasons.find(([rx]) => rx.test(s))?.[1] ||
    (/[가-힣]/.test(s) && !/[{}\x60]/.test(s)
      ? s
      : "확인 가능한 근거가 없습니다.")
  );
}
function disclosure(title, ...children) {
  const d = el("details");
  d.append(el("summary", title), ...children);
  return d;
}
function disclosureKey(node) {
  const parts = [];
  for (let d = node; d; d = d.parentElement?.closest("details")) {
    parts.unshift(d.querySelector("summary").textContent);
  }
  return parts.join("/");
}
function storedOpen(id) {
  try {
    return JSON.parse(sessionStorage.getItem("lab-open-" + id)) || [];
  } catch {
    return [];
  }
}
function saveOpen(id, target) {
  try {
    sessionStorage.setItem(
      "lab-open-" + id,
      JSON.stringify(
        [...target.querySelectorAll("details[open]")].map(disclosureKey),
      ),
    );
  } catch {
    /* Browsers may restrict storage in embedded views. */
  }
}
function persistView(id) {
  const url = new URL(location.href);
  for (const key of ["market", "from_date", "to_date", "case", "pages"])
    url.searchParams.delete(key);
  for (const [k, v] of filters) url.searchParams.set(k, v);
  if (id) url.searchParams.set("case", id);
  if (cursors.length > 1)
    url.searchParams.set("pages", cursors.slice(1).join(","));
  history.replaceState(null, "", url);
}
function facts(entries) {
  const list = el("dl", null, "facts");
  for (const [label, value] of entries) {
    const cell = el("div");
    cell.append(el("dt", label), el("dd", value ?? "—"));
    list.append(cell);
  }
  return list;
}
function table(headings, rows, title) {
  const frame = el("div", null, "table-scroll");
  frame.setAttribute("role", "region");
  frame.setAttribute("aria-label", title);
  frame.tabIndex = 0;
  const t = el("table"),
    h = el("thead"),
    tr = el("tr"),
    body = el("tbody");
  for (const v of headings) {
    const th = el("th");
    th.scope = "col";
    inline(th, String(v));
    tr.append(th);
  }
  h.append(tr);
  for (const values of rows) {
    const row = el("tr");
    for (const v of values) {
      const td = el("td");
      inline(td, String(v));
      row.append(td);
    }
    body.append(row);
  }
  t.append(h, body);
  frame.append(t);
  return frame;
}
// Build a deliberately small Markdown vocabulary with DOM text nodes. Model output
// cannot introduce HTML elements, href/src attributes, embedded media, or event handlers.
function inline(node, text) {
  text = text
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<\/?[a-z][a-z0-9-]*(?:\s[^<>]*?)?\s*\/?>/gi, "")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\bFINAL TRANSACTION PROPOSAL\s*:/gi, "최종 거래 의견 ·")
    .replace(/forecast_5s\.p_up|\bp_up\b/g, "5거래일 상승 확률");
  const tokens =
    /(\*\*([^\n]+?)\*\*|__([^\n]+?)__|\x60([^\x60\n]+)\x60|\*([^*\n]+)\*)/g;
  let end = 0;
  for (const hit of text.matchAll(tokens)) {
    node.append(text.slice(end, hit.index));
    node.append(
      el(
        hit[2] || hit[3] ? "strong" : hit[5] ? "em" : "span",
        hit[2] || hit[3] || hit[4] || hit[5],
      ),
    );
    end = hit.index + hit[0].length;
  }
  node.append(text.slice(end));
}
function strategy(obj) {
  const rows = [];
  const action = { BUY: "매수", SELL: "매도", HOLD: "보유" }[obj.action];
  const confidence = { HIGH: "높음", MEDIUM: "중간", LOW: "낮음" }[
    obj.conviction
  ];
  if (action) rows.push(["판단", action]);
  if (confidence) rows.push(["확신도", confidence]);
  if (numeric(obj.allocation_pct))
    rows.push(["제안 비중", obj.allocation_pct + "%"]);
  const probability = obj.forecast_5s?.p_up ?? obj.probability;
  if (numeric(probability) && probability >= 0 && probability <= 1)
    rows.push(["상승 확률", pct(probability)]);
  return rows;
}
function report(value, depth = 0) {
  const out = el("div", null, "report");
  if (depth > 8 || value == null) return out;
  if (typeof value === "object") {
    if (Array.isArray(value)) {
      for (const v of value) out.append(report(v, depth + 1));
    } else {
      // Tool envelopes can contain internal arguments and execution metadata. Only
      // render designated user-facing response fields and known decision values.
      const body =
        value.content ??
        value.final_response ??
        value.output ??
        value.text ??
        value.rationale ??
        value.summary;
      if (body != null) out.append(report(body, depth + 1));
      const rows = strategy(value);
      if (rows.length) out.append(facts(rows));
    }
    return out;
  }
  if (typeof value !== "string" || !value.trim()) return out;
  const source = value.trim();
  if (/^[{[]/.test(source)) {
    try {
      return report(JSON.parse(source), depth + 1);
    } catch {
      /* A structured block can be followed by ordinary prose. */
    }
  }
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const cell = (s) =>
    s
      .trim()
      .replace(/^\||\|$/g, "")
      .split("|")
      .map((v) => v.trim());
  const bullet = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line || /^([-*_])\1{2,}$/.test(line)) {
      i++;
      continue;
    }
    if (/^(?:\{\s*(?:"|$)|\[\s*(?:\{|$))/.test(line)) {
      let raw = "",
        object;
      // Preserve narrative outside standalone machine-generated blocks; never
      // print a partial envelope or arbitrary model/tool fields as fallback text.
      while (i < lines.length) {
        raw += lines[i++] + "\n";
        try {
          object = JSON.parse(raw);
          break;
        } catch {
          if (!lines[i]?.trim() || raw.length > 150000) break;
        }
      }
      if (object) out.append(report(object, depth + 1));
      continue;
    }
    if (/^(?:\x60{3}|~~~)/.test(line)) {
      const fence = line.slice(0, 3);
      const body = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith(fence); i++)
        body.push(lines[i]);
      i++;
      try {
        out.append(report(JSON.parse(body.join("\n")), depth + 1));
      } catch {
        /* Raw tool arguments, code and malformed strategies are not narrative. */
      }
      continue;
    }
    if (
      line.includes("|") &&
      i + 1 < lines.length &&
      cell(lines[i + 1]).every((v) => /^:?-{2,}:?$/.test(v))
    ) {
      const headings = cell(line),
        rows = [];
      i += 2;
      while (i < lines.length && lines[i].includes("|"))
        rows.push(cell(lines[i++]));
      out.append(table(headings, rows, "리포트 표"));
      continue;
    }
    const header = line.match(/^#{1,6}\s+(.+)/);
    if (header) {
      const h = el("h5");
      inline(h, header[1]);
      out.append(h);
      i++;
      continue;
    }
    const match = lines[i].match(bullet);
    if (match) {
      const ordered = /^\d/.test(match[2]),
        list = el(ordered ? "ol" : "ul");
      if (ordered) list.start = Number.parseInt(match[2], 10);
      while (i < lines.length) {
        const m = lines[i].match(bullet);
        if (!m || /^\d/.test(m[2]) !== ordered) break;
        const item = el("li");
        inline(item, m[3]);
        list.append(item);
        i++;
      }
      out.append(list);
      continue;
    }
    const quote = /^>\s*/.test(line);
    const prose = el(quote ? "blockquote" : "p");
    const para = [line.replace(/^>\s*/, "")];
    while (
      ++i < lines.length &&
      lines[i].trim() &&
      !/^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|~~~|\x60{3}|[|{])/.test(lines[i])
    ) {
      if (
        i + 1 < lines.length &&
        lines[i].includes("|") &&
        lines[i + 1].includes("--")
      )
        break;
      para.push(lines[i].trim());
    }
    inline(prose, para.join(" "));
    out.append(prose);
  }
  return out;
}
function priceRows(rows, currency) {
  return table(
    ["거래일", "시가", "고가", "저가", "종가", "거래량"],
    [...rows]
      .reverse()
      .map((r) => [
        r.date,
        ...["open", "high", "low", "close"].map((k) => amount(r[k], currency)),
        integer(r.volume),
      ]),
    "거래일별 시세 · 최신순",
  );
}
function marketFacts(s) {
  const f = s.features ?? {},
    b = s.benchmark ?? {},
    bars = s.bars ?? [],
    latest = bars.at(-1);
  const children = [
    facts([
      [
        "거래소",
        { XKRX: "한국거래소", XNYS: "미국 정규장" }[s.exchange] ?? "미확인",
      ],
      ["거래 통화", s.currency],
      ["자산 유형", { EQUITY: "주식", ETF: "상장지수펀드" }[s.instrument]],
      ["기준일 종가", amount(latest?.close, s.currency)],
      ["20거래일 가격 변화", pct(f.trend_20d)],
      ["20거래일 일간 변동성", pct(f.volatility_20d)],
    ]),
    el(
      "p",
      "시세 출처 · " +
        (s.source?.includes("NAVER")
          ? "네이버 금융 일봉. 야후 파이낸스의 배당·분할 기록과 대조했습니다."
          : s.source?.includes("Yahoo")
            ? "야후 파이낸스의 배당 재투자 조정을 적용하지 않은 일봉입니다."
            : "확인되지 않았습니다."),
    ),
  ];
  if (b.status === "available") {
    children.push(
      facts([
        ["시장 기준 종목", b.ticker],
        ["기준 종목 20거래일 변화", pct(f.benchmark_trend_20d)],
        ["기준 종목 일간 변동성", pct(f.benchmark_volatility_20d)],
        [
          "시장 대비 변화",
          numeric(f.relative_trend_20d)
            ? (100 * f.relative_trend_20d).toFixed(1) + "%p"
            : "—",
        ],
      ]),
    );
    if (b.bars?.length)
      children.push(
        disclosure("시장 기준 종목의 일별 시세", priceRows(b.bars, s.currency)),
      );
  } else
    children.push(
      el(
        "p",
        (b.ticker ? b.ticker + " · " : "") +
          "시장 비교 자료 없음. " +
          (b.reason ? why(b.reason) : ""),
      ),
    );
  if (bars.length)
    children.push(
      disclosure(
        "종목의 일별 시세 (" + bars.length + "거래일)",
        priceRows(bars, s.currency),
      ),
    );
  return disclosure("동결된 시장 근거", ...children);
}
function memoryDetails(m, title = "예측에 사용한 과거 사례") {
  return disclosure(
    title,
    facts([
      ["종목", m.ticker],
      ["관측 기준일", m.data_session],
      ["당시 예측", pct(m.probability)],
      ["실제 결과", upLabel(m.actual)],
      [
        "첫 거래일 시가",
        amount(m.entry_open, m.market === "kr" ? "KRW" : "USD"),
      ],
      [
        "다섯 번째 종가",
        amount(m.exit_close, m.market === "kr" ? "KRW" : "USD"),
      ],
      ["당시 20거래일 가격 변화", pct(m.features?.trend_20d)],
      ["당시 일간 변동성", pct(m.features?.volatility_20d)],
      ["당시 Brier", num(m.brier)],
      ["기억을 사용할 수 있게 된 시각", kst(m.created_at)],
    ]),
    report(m.rationale),
  );
}
function renderCase(target, c) {
  const s = c.snapshot ?? {};
  target.replaceChildren(
    el(
      "h3",
      [c.ticker, { us: "미국", kr: "한국" }[c.market], c.data_session]
        .filter(Boolean)
        .join(" · "),
    ),
    el(
      "p",
      (labels[c.status] ?? "상태 미확인") +
        " · " +
        versionLabel(c.experiment_version),
      "label",
    ),
    facts([
      ["근거 동결", kst(s.observed_at ?? c.created_at)],
      ["진입 시가 관측", kst(s.entry_open_at)],
      ["다섯 번째 종가 관측", kst(s.exit_close_at)],
    ]),
    marketFacts(s),
    el("h3", "방법별 예측"),
  );
  for (const method of ["baseline", "single", "debate", "memory"]) {
    const a = (c.arms ?? []).find((row) => row.method === method);
    const block = el("section", null, "arm");
    block.append(
      el("h4", names[method]),
      el(
        "span",
        a ? (labels[a.status] ?? "상태 미확인") : "발행 기록 없음",
        "arm-status",
      ),
    );
    if (a?.status === "published") {
      block.append(
        el("strong", "상승 확률 " + pct(a.probability), "probability"),
        el("small", modelLabel(a.model) + " · 발행 " + kst(a.published_at)),
      );
      const narrative = report(a.rationale);
      if (narrative.textContent.trim()) block.append(narrative);
      else block.append(el("p", "기록된 판단 근거가 없습니다."));
      if (a.brier != null) block.append(el("p", "관측 Brier " + num(a.brier)));
      const debate = a.audit?.debate;
      if (Array.isArray(debate) && debate.length) {
        const transcripts = debate.map((item, index) => {
          const body = report(item.output);
          if (!body.textContent.trim())
            body.append(el("p", "공개된 발언 내용이 없습니다."));
          return disclosure(
            index + 1 + ". " + (roles[item.role] || "토론 참여자"),
            body,
          );
        });
        block.append(
          disclosure(
            "역할별 토론 읽기 (" + transcripts.length + "개 발언)",
            ...transcripts,
          ),
        );
      }
      if (method === "memory" && c.selected_memory) {
        block.append(memoryDetails(c.selected_memory));
        const selection = a.audit?.memory_selection_v1;
        if (selection && numeric(selection.uplift_support))
          block.append(
            el(
              "small",
              "선택 시 이전 비교 " +
                selection.uplift_support +
                "건 · 보정 개선량 " +
                num(selection.shrunk_uplift),
            ),
          );
      }
    } else if (a) block.append(el("p", why(a.error || a.rationale)));
    target.append(block);
  }
  target.append(el("h3", "실제 관측 결과"));
  const o = c.outcome;
  if (o?.status === "scored") {
    target.append(
      facts([
        ["실제 방향", upLabel(o.actual)],
        ["첫 거래일 시가", amount(o.entry_open, s.currency)],
        ["다섯 번째 종가", amount(o.exit_close, s.currency)],
        ["채점 시각", kst(o.observed_at)],
      ]),
    );
    const bars = o.evidence?.evidence?.bars ?? o.evidence?.bars;
    if (bars?.length)
      target.append(
        disclosure("결과를 확인한 일별 시세", priceRows(bars, s.currency)),
      );
  } else
    target.append(
      el(
        "p",
        o
          ? "평가 제외 · " + why(o.reason)
          : "다섯 번째 거래일의 종가를 확인한 뒤 채점합니다.",
      ),
    );
  if (c.reference)
    target.append(
      disclosure(
        "같은 기간의 기존 운영 예측",
        facts([
          ["상승 확률", pct(c.reference.probability)],
          ["모델", modelLabel(c.reference.model)],
          ["기존 리포트 발행", kst(c.reference.source_published_at)],
          ["연구실 관측", kst(c.reference.captured_at)],
        ]),
      ),
    );
  if (c.memory)
    target.append(memoryDetails(c.memory, "이 사례에서 생성한 연구용 기억"));
}
async function get(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error("조회 실패 (" + response.status + ")");
  return response.json();
}
async function showCase(id) {
  const serial = ++activeRequest;
  selected = id;
  try {
    const c = await get("/api/cases/" + id);
    if (serial !== activeRequest) return;
    for (const b of $("cases").querySelectorAll("button"))
      b.setAttribute(
        "aria-pressed",
        String(Number(b.dataset.id) === Number(id)),
      );
    const target = $("detail");
    const key = JSON.stringify(c);
    if (key === detailKey) return;
    const sameCase = target.dataset.caseId === String(id);
    const existing = sameCase ? [...target.querySelectorAll("details")] : [];
    const open = new Set(existing.filter((d) => d.open).map(disclosureKey));
    const focus = existing
      .find((d) => d.querySelector("summary") === document.activeElement)
      ?.querySelector("summary").textContent;
    renderCase(target, c);
    const saved = storedOpen(id);
    for (const d of target.querySelectorAll("details")) {
      const summary = d.querySelector("summary");
      const key = disclosureKey(d);
      d.open = sameCase ? open.has(key) : saved.includes(key);
      d.addEventListener("toggle", () => {
        if (d.isConnected && target.dataset.caseId === String(id))
          saveOpen(id, target);
      });
      if (summary.textContent === focus) summary.focus({ preventScroll: true });
    }
    target.dataset.caseId = id;
    detailKey = key;
  } catch (e) {
    if (serial === activeRequest) $("error").textContent = e.message;
  }
}
async function refresh() {
  const serial = ++refreshSerial;
  const archive = new URLSearchParams(filters);
  archive.set("limit", pageSize + 1);
  if (cursors.at(-1)) archive.set("before_id", cursors.at(-1));
  try {
    const [s, stats, raw] = await Promise.all(
      ["/api/status", "/api/stats?" + filters, "/api/cases?" + archive].map(
        get,
      ),
    );
    if (serial !== refreshSerial) return;
    const list = raw.slice(0, pageSize);
    $("error").textContent = "";
    const p = s.progress ?? {};
    $("runtime").textContent = s.scheduler_enabled
      ? "자동 관측 켜짐"
      : "자동 관측 꺼짐";
    $("tickers").textContent =
      s.tickers.map((t) => t.ticker).join(", ") +
      "\n최근 작업 " +
      ({
        idle: "대기 중",
        maturing: "만기 확인",
        issuing: "예측 발행",
        busy: "다른 관측 진행 중",
        failed: "작업 실패",
      }[p.phase] ?? "시작 대기") +
      (p.ticker ? " · " + p.ticker : "") +
      (p.method ? " · " + (names[p.method] ?? p.method) : "");
    if (p.finished_at || p.started_at)
      $("tickers").append(
        el(
          "div",
          (p.finished_at ? "최근 작업 종료 " : "작업 시작 ") +
            kst(p.finished_at ?? p.started_at),
        ),
      );
    if (Object.keys(p.failures ?? {}).length)
      $("tickers").append(
        el(
          "p",
          "최근 수집 보류 · " +
            Object.entries(p.failures)
              .map(([t, r]) => t + " (" + why(r) + ")")
              .join(", "),
        ),
      );
    $("counts").replaceChildren();
    for (const [label, value] of [
      ["관찰 종목", s.tickers.length],
      ...["pending", "awaiting", "matured", "excluded", "unpublished"].map(
        (k) => [labels[k], stats.counts?.[k] ?? 0],
      ),
    ]) {
      const node = el("div", null, "tile");
      node.append(el("small", label), el("strong", value));
      $("counts").append(node);
    }
    $("comparisons").replaceChildren();
    for (const r of stats.comparisons ?? []) {
      const box = el("div", null, "comparison");
      box.append(
        el(
          "strong",
          names[r.control] + " → " + names[r.treated] + " · 공통 " + r.n + "건",
        ),
        el(
          "div",
          "Brier " +
            num(r.control_brier) +
            " → " +
            num(r.treated_brier) +
            " · 개선량 " +
            num(r.improvement),
        ),
        el(
          "small",
          [
            modelLabel(r.control_model),
            versionLabel(r.control_version),
            modelLabel(r.treated_model),
            versionLabel(r.treated_version),
            versionLabel(r.experiment_version),
          ]
            .filter(Boolean)
            .join(" / "),
        ),
      );
      if (r.distinct_entry_dates != null)
        box.append(
          el(
            "div",
            "서로 다른 진입일 " +
              r.distinct_entry_dates +
              "일 · 종목 " +
              r.distinct_tickers +
              "개",
          ),
        );
      if (r.control_paper_return != null)
        box.append(
          el(
            "div",
            "모의 총수익률 평균 " +
              pct(r.control_paper_return) +
              " → " +
              pct(r.treated_paper_return) +
              " (확률 50% 초과 시 보유, 그 외 현금)",
          ),
        );
      $("comparisons").append(box);
    }
    if (!$("comparisons").children.length)
      $("comparisons").append(el("p", "공통으로 채점된 사례가 아직 없습니다."));
    $("reference").replaceChildren();
    for (const r of stats.reference_comparisons ?? []) {
      const box = el("div", null, "comparison");
      box.append(
        el(
          "strong",
          "운영 모델 → " +
            names[r.method] +
            " · 공통 " +
            r.n +
            "건 · 진입일 " +
            r.distinct_entry_dates +
            "일",
        ),
        el(
          "p",
          "Brier " +
            num(r.source_brier) +
            " → " +
            num(r.method_brier) +
            " · 개선량 " +
            num(r.improvement),
        ),
        el(
          "small",
          [
            r.source_model,
            r.model,
            versionLabel(r.version),
            versionLabel(r.experiment_version),
          ]
            .filter(Boolean)
            .join(" / "),
        ),
      );
      $("reference").append(box);
    }
    if (!$("reference").children.length)
      $("reference").append(
        el(
          "p",
          s.reference_enabled
            ? "같은 기간에 발행하고 채점한 공통 표본이 아직 없습니다."
            : "기존 운영 리포트 수집이 꺼져 있습니다.",
        ),
      );
    $("calibration").replaceChildren();
    for (const r of stats.calibration ?? []) {
      const line = el(
        "p",
        names[r.method] +
          " · " +
          pct(r.lower) +
          "~" +
          pct(r.upper) +
          " · 평균 예측 " +
          pct(r.mean_probability) +
          " / 실제 상승 " +
          pct(r.observed_rate) +
          " · " +
          r.n +
          "건",
      );
      line.append(
        el(
          "small",
          " · " +
            [
              r.model,
              versionLabel(r.version),
              versionLabel(r.experiment_version),
            ]
              .filter(Boolean)
              .join(" / "),
        ),
      );
      $("calibration").append(line);
    }
    if (!$("calibration").children.length)
      $("calibration").append(
        el("p", "확률 구간을 평가할 관측 표본이 아직 없습니다."),
      );
    lastId = list.at(-1)?.id;
    $("prev").disabled = cursors.length <= 1;
    $("next").disabled = raw.length <= pageSize;
    $("page").textContent = cursors.length + "페이지 · " + list.length + "건";
    const key = JSON.stringify(list);
    if (key !== listKey) {
      const focused = document.activeElement?.dataset.id;
      $("cases").replaceChildren();
      for (const c of list) {
        const b = el(
          "button",
          msg(c.ticker, c.data_session) +
            " · " +
            (labels[c.status] ?? c.status),
        );
        b.append(
          el(
            "small",
            " · " + (versionLabel(c.experiment_version) ?? "버전 미확인"),
          ),
        );
        b.type = "button";
        b.dataset.id = c.id;
        b.setAttribute("aria-pressed", String(selected === c.id));
        b.onclick = () => {
          persistView(c.id);
          showCase(c.id);
        };
        $("cases").append(b);
        if (focused === String(c.id)) b.focus({ preventScroll: true });
      }
      if (!list.length)
        $("cases").append(el("p", "아직 발행 사례가 없습니다."));
      listKey = key;
    }
    if (list.length) await showCase(selected ?? list[0].id);
    else {
      detailKey = "";
      $("detail").replaceChildren(
        el("p", "선택한 조건에 맞는 사례가 없습니다."),
      );
    }
  } catch (e) {
    if (serial === refreshSerial) {
      $("error").textContent = e.message;
      $("page").textContent = "조회 실패";
    }
  }
}
function changePage() {
  selected = null;
  persistView(null);
  ++activeRequest;
  listKey = "";
  detailKey = "";
  $("page").textContent = "불러오는 중";
  $("next").disabled = true;
  $("prev").disabled = true;
  refresh();
}
$("filters").onsubmit = (event) => {
  event.preventDefault();
  const start = $("from-date").value,
    end = $("to-date").value;
  if (start && end && start > end) {
    $("error").textContent = "시작일이 종료일보다 늦습니다.";
    return;
  }
  filters = new URLSearchParams();
  for (const [key, value] of [
    ["market", $("market").value],
    ["from_date", start],
    ["to_date", end],
  ]) {
    if (value) filters.set(key, value);
  }
  cursors = [null];
  changePage();
};
$("prev").onclick = () => {
  if (cursors.length > 1) {
    cursors.pop();
    changePage();
  }
};
$("next").onclick = () => {
  if (lastId) {
    cursors.push(lastId);
    changePage();
  }
};
async function poll() {
  await refresh();
  setTimeout(poll, 15000);
}
for (const [param, id] of [
  ["market", "market"],
  ["from_date", "from-date"],
  ["to_date", "to-date"],
]) {
  if (route.get(param)) {
    $(id).value = route.get(param);
    if ($(id).value) filters.set(param, $(id).value);
  }
}
const cursorParam = route.get("pages") || "";
if (/^\d+(,\d+)*$/.test(cursorParam))
  cursors.push(...cursorParam.split(",").slice(0, 200));
if (/^\d+$/.test(route.get("case") || "")) selected = Number(route.get("case"));
poll();
