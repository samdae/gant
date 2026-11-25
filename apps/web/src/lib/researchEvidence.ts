import { isPublicViewer } from "./workspace";
export type Arm = {
  method: string;
  status: string;
  probability?: number | null;
  brier?: number | null;
  published_at?: string;
};
export type CaseRow = {
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
    publisher: string;
    url: string;
    published_at: string;
    published_day?: string | null;
    published_precision?: string;
    first_seen_at: string;
  }[];
};
export type ResearchCase = CaseRow & {
  snapshot?: {
    observed_at?: string;
    data_session?: string;
    entry_open_at?: string;
    exit_close_at?: string;
    currency?: string;
    source?: string;
    bars?: { close: number }[];
  };
  arms?: Arm[];
  outcome?: {
    status: string;
    actual?: number | null;
    entry_open?: number;
    exit_close?: number;
  } | null;
  hypothesis?: Hypothesis | null;
  issues?: Issues | null;
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
  return row.status === "pending" && published ? "일부 방법 발행" : stateName(row.status);
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
