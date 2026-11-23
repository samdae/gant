"use strict";
const $ = (id) => document.getElementById(id);
const names = {
  baseline: "빈도 기준선",
  single: "단일 모델",
  debate: "강세·약세 토론",
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
  v === "direction-5s-v1"
    ? v + " (초기 시범)"
    : v === "direction-5s-v2"
      ? v + " (분할·배당 확인)"
      : v;
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
function evidence(title, data) {
  const box = el("details");
  box.append(
    el("summary", title),
    el("pre", JSON.stringify(data ?? {}, null, 2)),
  );
  return box;
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
      b.setAttribute("aria-pressed", String(Number(b.dataset.id) === id));
    const target = $("detail");
    const key = JSON.stringify(c);
    if (key === detailKey) return;
    const sameCase = target.dataset.caseId === String(id);
    const existing = sameCase ? [...target.querySelectorAll("details")] : [];
    const open = new Set(
      existing
        .filter((d) => d.open)
        .map((d) => d.querySelector("summary").textContent),
    );
    const focus = existing
      .find((d) => d.querySelector("summary") === document.activeElement)
      ?.querySelector("summary").textContent;
    const snap = c.snapshot ?? {};
    target.replaceChildren(
      el(
        "h3",
        [c.ticker, { us: "미국", kr: "한국" }[c.market], c.data_session]
          .filter(Boolean)
          .join(" · "),
      ),
      el(
        "p",
        "상태 " +
          (labels[c.status] ?? c.status) +
          " · 실험 " +
          versionLabel(c.experiment_version),
        "label",
      ),
      el(
        "p",
        "진입 " +
          kst(snap.entry_open_at) +
          "\n만기 " +
          kst(snap.exit_close_at) +
          "\n근거 동결 " +
          kst(snap.observed_at ?? c.created_at),
      ),
      evidence("동결된 시장 근거 · 시세 출처 및 특징", snap),
    );
    const bench = snap.benchmark;
    if (bench)
      target.append(
        el(
          "p",
          "시장 기준 " +
            bench.ticker +
            " · " +
            (bench.status === "available" ? "관측됨" : "자료 부족") +
            (snap.features?.benchmark_trend_20d != null
              ? " · 20거래일 변화 " + pct(snap.features.benchmark_trend_20d)
              : ""),
        ),
      );
    for (const a of c.arms ?? []) {
      const block = el("div", null, "arm");
      block.append(
        el(
          "strong",
          msg(names[a.method] ?? a.method, labels[a.status] ?? a.status),
        ),
        el(
          "p",
          "상승 확률 " +
            pct(a.probability) +
            " · " +
            (a.model || "—") +
            " · " +
            (a.version || "—"),
        ),
        el("p", a.rationale || a.error || "근거 대기"),
      );
      if (a.brier != null) block.append(el("p", "관측 Brier " + num(a.brier)));
      if (a.published_at)
        block.append(el("small", "발행 " + kst(a.published_at)));
      if (a.audit)
        block.append(
          evidence((names[a.method] ?? a.method) + " 발행 근거", a.audit),
        );
      target.append(block);
    }
    if (c.outcome) {
      const o = c.outcome;
      target.append(
        el(
          "p",
          o.status === "scored"
            ? "실제 결과 " +
                (o.actual === 1 ? "상승" : "보합 또는 하락") +
                " · 진입 시가 " +
                o.entry_open +
                " → 다섯 번째 종가 " +
                o.exit_close
            : "평가 제외 · " + (o.reason ?? "사유 미확인"),
        ),
        evidence("결과 · 관측 가격 및 채점 근거", o),
      );
    } else target.append(el("p", "관측 결과 대기"));
    if (c.selected_memory) {
      const m = c.selected_memory;
      target.append(
        el("h3", "이 판단에 쓰인 기억"),
        el(
          "p",
          m.ticker +
            " · " +
            m.data_session +
            " · 당시 예측 " +
            pct(m.probability) +
            " · 실제 " +
            (m.actual === 1 ? "상승" : "보합 또는 하락"),
        ),
        el("p", m.rationale),
        el(
          "small",
          "선택 전 공통 " +
            (m.uplift_support ?? 0) +
            "건 · 보정 개선량 " +
            num(m.shrunk_uplift),
        ),
        evidence("적용한 기억의 전체 기록", m),
      );
    }
    if (c.reference)
      target.append(evidence("기존 운영 리포트에서 관측한 확률", c.reference));
    if (c.memory)
      target.append(evidence("이 사례에서 생성된 후속 연구용 기억", c.memory));
    for (const d of target.querySelectorAll("details")) {
      const summary = d.querySelector("summary");
      d.open = open.has(summary.textContent);
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
      (p.phase ?? "시작 대기") +
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
              .map(([t, r]) => t + " (" + r + ")")
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
            r.control_model,
            r.control_version,
            r.treated_model,
            r.treated_version,
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
            r.version,
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
            [r.model, r.version, versionLabel(r.experiment_version)]
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
        b.onclick = () => showCase(c.id);
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
poll();
