"use strict";

const main = document.getElementById("content");
const methods = {
  baseline: "빈도 기준선",
  single: "단일 모델",
  debate: "역할 토론",
  memory: "과거 기억을 본 모델",
  memory_sector: "종목 분류로 기억을 고른 모델",
};
const states = {
  pending: "예측 발행 대기",
  awaiting: "만기 대기",
  matured: "채점 완료",
  excluded: "평가 제외",
  unpublished: "미발행",
};
const decisions = {
  BUY: "매수",
  SELL: "매도",
  HOLD: "관망",
  매수: "매수",
  매도: "매도",
  관망: "관망",
  보유: "관망",
};
const markets = { kr: "한국", us: "미국", crypto: "디지털자산" };
const labels = {
  research: "종목 예측",
  reports: "연구 리포트",
  results: "기억 활용 성과",
};
const dateTime = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
let generation = 0;

function node(tag, text, cls) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (cls) element.className = cls;
  return element;
}
function link(text, href, cls) {
  const a = node("a", text, cls);
  a.href = href;
  return a;
}
function stamp(value) {
  if (!value) return "미기록";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? dateTime.format(date) + " KST"
    : "미기록";
}
function prob(value) {
  return Number.isFinite(value) ? (value * 100).toFixed(1) + "%" : "미기록";
}
function score(value) {
  return Number.isFinite(value) ? value.toFixed(3) : "미기록";
}
function identity(item) {
  const wrap = node("span", null, "identity");
  const ticker = String(item.ticker || "");
  const name = item.name?.trim();
  wrap.append(node("strong", name || ticker || "종목 미기록"));
  const detail = [
    name && name.toUpperCase() !== ticker.toUpperCase() ? ticker : "",
    markets[item.market],
  ]
    .filter(Boolean)
    .join(" · ");
  if (detail) wrap.append(node("small", detail));
  return wrap;
}
function intro(title, text) {
  const el = node("header", null, "intro");
  el.append(node("h1", title));
  if (text) el.append(node("p", text));
  return el;
}
function panel(title) {
  const el = node("section", null, "panel");
  if (title) el.append(node("h2", title));
  return el;
}
function facts(pairs) {
  const box = node("dl", null, "grid");
  for (const [label, value] of pairs) {
    const item = node("div");
    item.append(node("dt", label), node("dd", value ?? "미기록"));
    box.append(item);
  }
  return box;
}
function status(text) {
  const p = node("p", text, "empty");
  p.setAttribute("role", "status");
  return p;
}
async function get(path) {
  const result = await fetch("/public-api/" + path, {
    credentials: "omit",
    headers: { Accept: "application/json" },
  });
  if (!result.ok)
    throw new Error(
      result.status === 404
        ? "공개된 자료를 찾을 수 없습니다."
        : "자료를 불러오지 못했습니다.",
    );
  return result.json();
}
function row(item, view) {
  const report = view === "reports";
  const a = link(null, "#/" + view + "/" + encodeURIComponent(item.id), "row");
  const cell = node("span", null, "cell");
  cell.append(
    node("small", report ? "발행 시각" : "관측 기준일"),
    node("span", stamp(report ? item.created_at : item.data_session)),
  );
  a.append(
    identity(item),
    cell,
    node(
      "span",
      report
        ? decisions[item.decision] || "판단 미기록"
        : states[item.status] || "상태 미확인",
      "state pill",
    ),
    node("span", "›", "arrow"),
  );
  return a;
}
function list(view, rows) {
  const report = view === "reports";
  const title = intro(
    labels[view],
    report
      ? "종목별 연구 요약과 판단 근거를 발행일 순으로 확인합니다."
      : "개장 전에 발행한 상승 확률과 다섯 번째 거래일에 확인한 결과입니다.",
  );
  const box = panel(),
    tools = node("div", null, "toolbar"),
    count = node("h2");
  const filters = node("div", null, "filters"),
    search = node("input"),
    market = node("select");
  search.type = "search";
  search.placeholder = "종목명 또는 티커 검색";
  search.setAttribute("aria-label", search.placeholder);
  market.setAttribute("aria-label", "시장 선택");
  market.append(new Option("전체 시장", ""));
  const present = new Set(rows.map((item) => item.market));
  for (const [key, label] of Object.entries(markets)) {
    if (present.has(key) && (report || key !== "crypto"))
      market.append(new Option(label, key));
  }
  const body = node("div");
  function draw() {
    const q = search.value.trim().toLowerCase();
    const visible = rows.filter(
      (r) =>
        (!market.value || market.value === r.market) &&
        [r.name, r.ticker].some((x) =>
          String(x || "")
            .toLowerCase()
            .includes(q),
        ),
    );
    count.textContent =
      "최근 공개 " +
      (report ? "리포트" : "예측") +
      " · " +
      visible.length +
      "건";
    body.replaceChildren(...visible.map((r) => row(r, view)));
    if (!visible.length)
      body.append(
        status(
          rows.length
            ? "조건에 맞는 종목이 없습니다."
            : "아직 공개한 자료가 없습니다.",
        ),
      );
  }
  search.oninput = draw;
  market.onchange = draw;
  filters.append(search, market);
  tools.append(count, filters);
  box.append(tools, body);
  draw();
  return [title, box];
}
function editorial(text) {
  if (typeof text !== "string") return "";
  const cleaned = text.trim();
  if (/^[{[]/.test(cleaned)) return "";
  return cleaned
    .replace(/^`{3}[^\n]*[\s\S]*?(?:^`{3}[^\n]*$|(?![\s\S]))/gm, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*([^*\n]+)\*\*/g, "$1")
    .trim();
}

function detail(item, view) {
  const report = view === "reports";
  const title = intro(item.name || item.ticker);
  const id = [
    item.name && item.name.toUpperCase() !== item.ticker?.toUpperCase()
      ? item.ticker
      : "",
    markets[item.market],
    report ? "연구 리포트" : "종목 예측",
  ]
    .filter(Boolean)
    .join(" · ");
  title.prepend(node("span", id, "meta"));
  const summary = panel(report ? "리포트 요약" : "예측 개요");
  const text = editorial(item.summary);
  if (text) summary.append(node("p", text, "copy"));
  summary.append(
    facts(
      report
        ? [
            ["발행 시각", stamp(item.created_at)],
            ["분석 판단", decisions[item.decision] || "미기록"],
          ]
        : [
            ["관측 기준일", stamp(item.data_session)],
            ["첫날 개장", stamp(item.entry_open_at)],
            ["다섯째 날 마감", stamp(item.exit_close_at)],
            ["상태", states[item.status] || "미확인"],
          ],
    ),
  );
  const children = [
    link("← " + labels[view] + " 목록", "#/" + view, "back"),
    title,
    summary,
  ];
  if (report) {
    for (const section of item.sections || []) {
      const text = editorial(section.text);
      if (!text) continue;
      const p = panel(editorial(section.title));
      p.append(node("p", text, "copy"));
      children.push(p);
    }
    return children;
  }
  const models = panel("방법별 상승 확률");
  for (const arm of item.forecasts || []) {
    const r = node("div", null, "forecast");
    r.append(
      node("strong", methods[arm.method] || "기타 방법"),
      node("strong", prob(arm.probability), "score"),
    );
    if (Number.isFinite(arm.probability)) {
      const bar = node("progress", null, "bar");
      bar.max = 1;
      bar.value = arm.probability;
      bar.setAttribute("aria-label", "상승 확률 " + prob(arm.probability));
      r.append(bar);
    }
    r.append(node("small", "발행 " + stamp(arm.published_at), "meta"));
    if (Number.isFinite(arm.brier))
      r.append(node("small", "Brier " + score(arm.brier), "meta"));
    models.append(r);
  }
  if (!item.forecasts?.length)
    models.append(status("공개된 예측 확률이 아직 없습니다."));
  const outcome = panel("실제 관측");
  if (item.outcome)
    outcome.append(
      facts([
        [
          "방향",
          item.outcome.actual === 1
            ? "상승"
            : item.outcome.actual === 0
              ? "보합 또는 하락"
              : "미확인",
        ],
        ["첫날 시가", item.outcome.entry_open],
        ["다섯째 날 종가", item.outcome.exit_close],
      ]),
    );
  else
    outcome.append(
      status(
        item.status === "excluded"
          ? "평가에서 제외한 사례입니다."
          : "공개된 만기 결과가 아직 없습니다.",
      ),
    );
  return [...children, models, outcome];
}
function performance(data) {
  const children = [
    intro(
      labels.results,
      "같은 종목·거래 기간에 발행한 예측을 짝지어, 과거 사례를 제공했을 때의 확률 점수를 비교합니다.",
    ),
  ];
  const coverage = data.sector_coverage;
  if (coverage) {
    const card = panel("종목 분류를 활용한 기억 선택");
    card.append(
      facts([
        ["대상 사례", coverage.eligible_cases],
        ["예측 발행", coverage.published],
        ["서로 다른 기억을 채점한 쌍", coverage.scored],
        ["같은 기억 선택", coverage.same_memory],
        ["적합한 기억 없음", coverage.no_eligible_sector_memory],
      ]),
    );
    children.push(card);
  }
  const box = panel("공통 표본의 Brier 점수");
  box.append(
    node(
      "p",
      "점수는 낮을수록 정확합니다. 개선량은 기준 점수에서 기억 활용 점수를 뺀 값입니다.",
      "copy",
    ),
  );
  const comparisons = (data.comparisons || []).filter(
    (r) =>
      ((r.control === "single" && r.treated === "memory") ||
        (r.control === "memory" && r.treated === "memory_sector")) &&
      r.n > 0,
  );
  for (const r of comparisons) {
    const line = node("section", null, "panel");
    line.append(node("h3", methods[r.control] + " → " + methods[r.treated]));
    line.append(
      facts([
        ["공통 채점", r.n + "쌍"],
        ["기준 점수", score(r.control_brier)],
        ["기억 활용 점수", score(r.treated_brier)],
        [
          "개선량",
          Number.isFinite(r.improvement)
            ? (r.improvement > 0 ? "+" : "") +
              score(r.improvement) +
              (r.improvement > 0
                ? " 개선"
                : r.improvement < 0
                  ? " 악화"
                  : " 차이 없음")
            : "미기록",
        ],
      ]),
    );
    if (r.experiment_version)
      line.append(
        node(
          "small",
          {
            "direction-5s-v1": "초기 실험",
            "direction-5s-v2": "분할·배당 확인 실험",
          }[r.experiment_version] || "별도 실험 집단",
          "meta",
        ),
      );
    box.append(line);
  }
  if (!comparisons.length)
    box.append(
      status(
        "두 방법 모두 발행되고 만기 가격이 확인된 비교 표본이 아직 없습니다.",
      ),
    );
  return [...children, box];
}
function route() {
  const hash = location.hash.slice(1).replace(/^\/?/, "").split("?")[0],
    parts = hash.split("/");
  const view =
    parts[0] === "reports"
      ? "reports"
      : ["results", "performance", "reflections"].includes(parts[0])
        ? "results"
        : "research";
  const id =
    parts[1] ||
    (view === "research" && new URLSearchParams(location.search).get("case"));
  return { view, id };
}
async function render() {
  const epoch = ++generation,
    { view, id } = route();
  document.title = labels[view] + " | TradingAgents";
  for (const a of document.querySelectorAll("[data-tab]")) {
    if (a.dataset.tab === view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  main.replaceChildren(status("자료를 불러오는 중입니다."));
  let children;
  try {
    if (view === "results") children = performance(await get("overview"));
    else if (id && /^[1-9]\d*$/.test(id))
      children = detail(
        await get((view === "reports" ? "reports/" : "cases/") + id),
        view,
      );
    else {
      const report = view === "reports",
        data = await get(report ? "reports" : "overview"),
        rows = (report ? data.reports : data.cases) || [];
      if (id && report) {
        const match = rows.find(
          (r) => r.ticker.toLowerCase() === id.toLowerCase(),
        );
        children = match
          ? detail(await get("reports/" + match.id), view)
          : [
              link("← 연구 리포트 목록", "#/reports", "back"),
              intro("종목 리포트"),
              status("최근 공개 목록에서 해당 종목을 찾을 수 없습니다."),
            ];
      } else children = list(view, rows);
    }
  } catch (e) {
    const retry = node("button", "다시 조회");
    retry.onclick = render;
    children = [
      intro(labels[view]),
      status(
        e instanceof TypeError ? "자료를 불러오지 못했습니다." : e.message,
      ),
      retry,
    ];
  }
  if (epoch === generation) main.replaceChildren(...children);
}
document.querySelector(".skip").addEventListener("click", (event) => {
  event.preventDefault();
  main.focus();
});
window.addEventListener("hashchange", () => {
  render();
  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);
});
render();
