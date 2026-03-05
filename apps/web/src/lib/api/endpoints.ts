import { deleteJson, getJson, postJson } from "./client";

export type ScheduleRequest = {
  ticker: string;
  interval_days?: number;
  display_name?: string;
};

export const fetchMetrics = () => getJson("/metrics");
export const fetchHealth = () => getJson("/health");
export const fetchPositionsMarket = () => getJson("/positions/market");
export const fetchPositionsClosed = () => getJson("/positions/closed");
export const fetchPositions = (status?: string) =>
  getJson(status ? `/positions?status=${encodeURIComponent(status)}` : "/positions");
export const fetchQueue = () => getJson("/queue");
export const fetchScheduleSummary = () => getJson("/schedules/summary");
export const fetchLiveEvents = (ticker: string, limit = 50) =>
  getJson(`/live/${encodeURIComponent(ticker)}/events?limit=${limit}`);
export const fetchActivity = () => getJson("/activity");
export const fetchSchedules = () => getJson("/schedules?limit=100");
export const fetchScheduleCycles = (ticker: string, limit = 1, cursor?: number) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", String(cursor));
  return getJson(`/schedules/${encodeURIComponent(ticker)}/cycles?${params.toString()}`);
};

export const fetchScheduleCycleEvents = (ticker: string, scheduleId: number, limit = 200) =>
  getJson(
    `/schedules/${encodeURIComponent(ticker)}/cycles/${scheduleId}/events?limit=${limit}`,
  );

export const createSchedule = (payload: ScheduleRequest) =>
  postJson("/schedules", payload);

export const deleteSchedule = (ticker: string) =>
  deleteJson(`/schedules/${ticker}`);

export const fetchReportsByTicker = (ticker: string, limit = 1) =>
  getJson(`/reports?ticker=${encodeURIComponent(ticker)}&limit=${limit}`);

export const fetchReportTickers = () =>
  getJson("/reports/tickers");

export const fetchPositionDetail = (id: number) =>
  getJson(`/positions/${id}`);

export const fetchPositionGraph = (id: number, days = 7) =>
  getJson(`/position/${id}/graph?days=${days}`);

export const searchTickers = (q: string) =>
  getJson(`/search/tickers?q=${encodeURIComponent(q)}`);

export const fetchReflections = (limit = 15, outcome?: string, cursor?: number) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (outcome) params.set("outcome", outcome);
  if (cursor) params.set("cursor", String(cursor));
  return getJson(`/reflections?${params.toString()}`);
};

export const fetchReflectionDetail = (reflectionId: number) =>
  getJson(`/reflections/detail/${reflectionId}`);

export const fetchRetroTickers = () => getJson("/retrospective/tickers");

export const fetchRetroSummary = () => getJson("/retrospective/summary");

export const fetchRetroByTicker = (ticker: string) =>
  getJson(`/retrospective/detail/${encodeURIComponent(ticker)}`);

export const fetchRetroPositions = (ticker: string) =>
  getJson(`/retrospective/positions/${encodeURIComponent(ticker)}`);

export const requestRetroAnalysis = (payload: {
  mode: string;
  position_ids?: number[];
  tickers?: string[];
  date_from?: string;
  date_to?: string;
}) => postJson("/retrospective/analyze", payload);

export const fetchRetroResult = (retroId: number) =>
  getJson(`/retrospective/${retroId}`);

// Portfolio
export const fetchPortfolioConfig = () => getJson("/portfolio/config");

export const createPortfolioConfig = (payload: {
  initial_capital: number;
  base_currency: "KRW" | "USD";
  fee_enabled?: boolean;
  reset_fund_to_initial?: boolean;
}) => postJson("/portfolio/config", payload);

export const fetchPortfolioHoldings = () => getJson("/portfolio/holdings");

export const fetchPortfolioTrades = (ticker?: string, cursor?: number, limit = 50) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (ticker) params.set("ticker", ticker);
  if (cursor) params.set("cursor", String(cursor));
  return getJson(`/portfolio/trades?${params.toString()}`);
};

export const fetchPortfolioClosedTickers = () => getJson("/portfolio/closed");
