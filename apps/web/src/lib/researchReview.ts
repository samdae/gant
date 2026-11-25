import { methodName } from "./researchEvidence";

export type Metric = {
  n?: number;
  distinct_tickers?: number;
  distinct_entry_dates?: number;
  lower?: number;
  upper?: number;
  mean_probability?: number;
  observed_rate?: number;
  control_brier?: number;
  treated_brier?: number;
  method_brier?: number;
  source_brier?: number;
  improvement?: number;
  control_paper_return?: number;
  treated_paper_return?: number;
  method?: string;
  control?: string;
  treated?: string;
  model?: string;
  source_model?: string;
  control_model?: string;
  treated_model?: string;
  version?: string;
  experiment_version?: string;
  control_version?: string;
  treated_version?: string;
  basis?: string;
};
export type Stats = {
  comparisons: Metric[];
  reference_comparisons: Metric[];
  calibration: Metric[];
  sector_by_basis: Metric[];
  counts: Record<string, number>;
  sector_coverage: Record<string, number>;
};
export type Watch = {
  ticker: string;
  market: string;
  name?: string;
  classification?: {
    asset_class?: string;
    sector?: string;
    exposure?: string;
  };
};
export type Status = {
  tickers: Watch[];
  scheduler_enabled: boolean;
  reference_enabled: boolean;
  progress: {
    phase?: string;
    ticker?: string;
    method?: string;
    started_at?: string;
    finished_at?: string;
    failures?: Record<string, string>;
    attempted?: number;
    total?: number;
  };
};
export const caseStates = {
  pending: "발행 진행",
  awaiting: "만기 대기",
  matured: "채점 완료",
  excluded: "평가 제외",
  unpublished: "마감까지 미발행",
};
export const coverageLabels = {
  eligible_cases: "분류 실험 대상",
  published: "확률 발행",
  same_memory: "기존과 동일한 기억",
  no_eligible_sector_memory: "적격 분류 기억 없음",
  failed: "발행 실패",
  pending: "발행 대기",
  expired_unpublished: "마감까지 미발행",
  scored: "서로 다른 기억의 채점 쌍",
};
export const phases: Record<string, string> = {
  idle: "대기 중",
  maturing: "만기 확인",
  issuing: "예측 발행",
  busy: "관측 진행 중",
  failed: "작업 실패",
};
const categories: Record<string, string> = {
  technology: "정보기술",
  industrials: "산업재",
  utilities: "유틸리티",
  energy: "에너지",
  financials: "금융",
  consumer_discretionary: "경기소비재",
  consumer_staples: "필수소비재",
  real_estate: "부동산",
  communication_services: "통신서비스",
  us_large_cap: "미국 대형주",
  kr_large_cap: "한국 대형주",
  gold: "금",
  silver: "은",
  us_tips: "미국 물가연동국채",
};
export function group(t: Watch) {
  const c = t.classification;
  if (c?.asset_class === "equity")
    return "주식 · " + (categories[c.sector || ""] || "섹터 미확인");
  if (c?.asset_class === "etf")
    return "ETF · " + (categories[c.exposure || ""] || "추종 자산 미확인");
  return "분류 미확인";
}
export const method = (v?: string) => (v ? methodName(v) : "방법 미기록");
export const score = (v?: number) =>
  typeof v === "number" && isFinite(v) ? v.toFixed(3) : "—";
export const pct = (v?: number) =>
  typeof v === "number" && isFinite(v) ? (100 * v).toFixed(1) + "%" : "—";
export const spec = (r: Metric) =>
  [
    r.source_model,
    r.control_model,
    r.control_version,
    r.treated_model,
    r.treated_version,
    r.model,
    r.version,
    r.experiment_version,
  ]
    .filter(Boolean)
    .join(" / ");
export const shared = (r: Metric) =>
  [
    r.n == null ? null : r.n + "건",
    r.distinct_entry_dates == null
      ? null
      : "진입 " + r.distinct_entry_dates + "일",
    r.distinct_tickers == null ? null : r.distinct_tickers + "종목",
  ]
    .filter(Boolean)
    .join(" · ");
export function basis(r: Metric) {
  return (
    {
      same_ticker: "동일 종목의 다른 회차",
      equity_peer: "동조 확인 동종주",
      etf_exposure: "동일 자산 추종 ETF",
    }[r.basis || ""] || "근거 미확인"
  );
}
export function holdReason(raw: string) {
  if (/deadline|entry session|window closed/i.test(raw))
    return "발행 시간 마감";
  if (/21-session|corporate.action|dividend|split/i.test(raw))
    return "연속 시세·기업행위 확인 필요";
  if (/incomplete|missing|price window|no verified/i.test(raw))
    return "시세 자료 부족";
  if (/calendar/i.test(raw)) return "거래소 일정 확인 필요";
  if (/timeout|time budget/i.test(raw)) return "응답 시간 초과";
  return "이번 관측 보류";
}
