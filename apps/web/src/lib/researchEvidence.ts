import { isPublicViewer } from "./workspace";
export type Arm = {
  method: string;
  status: string;
  probability?: number | null;
  brier?: number | null;
  published_at?: string;
  rationale?: string;
  model?: string;
  version?: string;
  error?: string;
  audit?: {
    debate?: { role: string; output: string }[];
    memory_selection_v1?: { uplift_support?: number; shrunk_uplift?: number };
    sector_selection_v1?: Selection;
  };
};
export type Selection = {
  basis?: string;
  selected_ticker?: string;
  peer_ticker?: string;
  peer_reference?: string;
  reference_count?: number;
  source_window_return?: number;
  peer_window_return?: number;
};
export type Bar = {
  date: string;
  close: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
};
export type Memory = {
  ticker: string;
  market?: string;
  data_session?: string;
  probability?: number;
  actual?: number;
  entry_open?: number;
  exit_close?: number;
  brier?: number;
  rationale?: string;
  created_at?: string;
  features?: { trend_20d?: number; volatility_20d?: number };
};
export type CaseRow = {
  experiment_version?: string;
  forecast_probabilities?: Record<string, number>;
  id: number;
  ticker: string;
  market: string;
  status: string;
  data_session: string;
  entry_open_at?: string;
  exit_close_at?: string;
};
export type Condition = {
  id: string;
  metric: string;
  operator: string;
  threshold: number;
  status: string;
  observed_value: number | null;
  observed_session: string | null;
};
export type Hypothesis = {
  version: string;
  data_session: string;
  observed_at: string;
  currency: string;
  source: string;
  reference_close: number;
  reference_window_start?: string;
  window_start: string;
  window_end: string;
  conditions: Condition[];
};
export type Issues = {
  as_of: string;
  status: string;
  collected_at: string | null;
  source: string;
  items: {
    title: string;
    source?: string;
    in_frozen_list?: boolean;
    publisher: string;
    url: string;
    published_at: string;
    published_day?: string | null;
    published_precision?: string;
    first_seen_at: string;
  }[];
};
export function caseSources(frozen?: Issues | null, collected?: Issues | null) {
  const rssSource = "Google News RSS";
  const exportSource = "last30days agent export";
  const rows = frozen?.items || [];
  const tagged = rows.filter(item => item.source === exportSource);
  const known = new Set(rows.map(item => item.url));
  const available = new Map<string, Issues["items"][number]>();
  for (const item of [...(collected?.items || []), ...tagged]) {
    if (available.has(item.url)) continue;
    available.set(item.url, { ...item, in_frozen_list: known.has(item.url) });
  }
  const exports = collected || (tagged.length ? frozen : undefined);
  const unmatched = rows.filter(item => item.source !== rssSource && item.source !== exportSource && !available.has(item.url));
  return {
    archives: exports ? { ...exports, source: exportSource, items: [...available.values()] } : undefined,
    rss: frozen ? { ...frozen, source: rssSource, items: rows.filter(item => item.source === rssSource && !available.has(item.url)) } : undefined,
    unmatched: frozen && unmatched.length ? { ...frozen, items: unmatched } : undefined,
  };
}
export type ResearchCase = CaseRow & {
  snapshot?: {
    observed_at?: string;
    data_session?: string;
    entry_open_at?: string;
    exit_close_at?: string;
    currency?: string;
    source?: string;
    bars?: Bar[];
    exchange?: string;
    instrument?: string;
    retrieval_policy?: string;
    features?: Record<string, number>;
    classification?: {
      asset_class?: string;
      sector?: string;
      industry?: string;
      exposure?: string;
    };
    benchmark?: { ticker?: string; status?: string; bars?: Bar[] };
  };
  arms?: Arm[];
  outcome?: {
    status: string;
    actual?: number | null;
    observed_at?: string;
    reason?: string;
    evidence?: { bars?: Bar[]; evidence?: { bars?: Bar[] } };
    entry_open?: number;
    exit_close?: number;
  } | null;
  hypothesis?: Hypothesis | null;
  issues?: Issues | null;
  last30days?: Issues | null;
  memory?: Memory | null;
  selected_memory?: Memory | null;
  selected_memories?: Record<string, Memory>;
  reference?: {
    probability?: number;
    model?: string;
    source_published_at?: string;
    captured_at?: string;
  } | null;
};
const states: Record<string, string> = {
  pending: "발행 대기",
  awaiting: "만기 대기",
  matured: "채점 완료",
  excluded: "평가 제외",
  unpublished: "미발행",
  published: "발행",
  failed: "발행 실패",
  skipped: "건너뜀",
  met: "충족",
  not_met: "미충족",
  unavailable: "평가 불가",
};
export const stateName = (value: string) => states[value] || "상태 미확인";
export function caseListStatus(row: CaseRow) {
  const published = Object.values(row.forecast_probabilities || {}).some(
    (value) => Number.isFinite(value) && value >= 0 && value <= 1,
  );
  return row.status === "pending" && published
    ? "일부 방법 발행"
    : stateName(row.status);
}
export const marketName = (value: string) =>
  ({ kr: "한국", us: "미국" })[value] || "시장 미확인";
export const methodName = (value: string) =>
  ({
    baseline: "빈도 기준선",
    single: "단일 모델",
    debate: "역할 토론",
    memory: "기억 제공 모델",
    memory_sector: "분류 기억 모델",
  })[value] || "기타 방법";
const timeFormat = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
export function timeLabel(value?: string | null) {
  if (!value) return "미기록";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "미기록" : timeFormat.format(d) + " KST";
}
export function price(value?: number | null, currency?: string) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "미기록";
  return (
    value.toLocaleString("ko-KR", { maximumFractionDigits: 4 }) +
    (currency === "KRW" ? "원" : currency === "USD" ? "달러" : "")
  );
}
export const probability = (value?: number | null) =>
  typeof value === "number" &&
  Number.isFinite(value) &&
  value >= 0 &&
  value <= 1
    ? (value * 100).toFixed(1) + "%"
    : "미발행";
export function articleUrl(value: string) {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password
      ? u.href
      : undefined;
  } catch {
    return undefined;
  }
}
export async function researchGet<T>(
  path: string,
  signal: AbortSignal,
): Promise<T> {
  const r = await fetch("/api/" + path, {
    signal,
    credentials: isPublicViewer ? "omit" : "same-origin",
    cache: "no-cache",
  });
  if (!r.ok)
    throw new Error(
      r.status === 404
        ? "이 사례를 찾을 수 없습니다."
        : "연구 자료를 불러오지 못했습니다.",
    );
  return r.json();
}

export const percentChange = (v?: number | null) =>
  typeof v === "number" && Number.isFinite(v)
    ? (100 * v).toLocaleString("ko-KR", { maximumFractionDigits: 2 }) + "%"
    : "미기록";

const sectorLabels: Record<string, string> = {
  technology: "정보기술",
  industrials: "산업재",
  utilities: "유틸리티",
  energy: "에너지",
  financials: "금융",
  consumer_discretionary: "경기소비재",
  consumer_staples: "필수소비재",
  real_estate: "부동산",
  communication_services: "통신서비스",
};
const industryLabels: Record<string, string> = {
  semiconductors: "반도체",
  diversified_electronics: "종합전자",
  automobiles: "자동차",
  aerospace_defense: "항공·방산",
  power_equipment: "발전·전력기기",
  gas_utilities: "가스공급",
  integrated_energy: "종합에너지",
  electrical_equipment: "전력기기",
  banking: "은행",
  data_center_reits: "데이터센터 리츠",
  solar_modules: "태양광 모듈",
  interactive_media: "인터넷 미디어",
  beverages: "음료",
  oil_gas: "석유·가스",
  power_generation: "발전",
  staples_retail: "생활필수품 유통",
};
const exposureLabels: Record<string, string> = {
  us_large_cap: "미국 대형주(S&P 500)",
  kr_large_cap: "한국 대형주(KOSPI 200)",
  gold: "금",
  silver: "은",
  us_tips: "미국 물가연동국채",
};

export function classificationLabel(
  cl: NonNullable<ResearchCase["snapshot"]>["classification"],
) {
  if (!cl) return "미기록";
  if (cl.asset_class === "equity")
    return [
      "주식",
      sectorLabels[cl.sector || ""] || "섹터 미분류",
      industryLabels[cl.industry || ""] || "산업 미분류",
    ].join(" · ");
  if (cl.asset_class === "etf")
    return "ETF · " + (exposureLabels[cl.exposure || ""] || "추종 자산 미분류");
  return "자산 유형 미확인";
}
