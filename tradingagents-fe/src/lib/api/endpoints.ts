import { deleteJson, getJson, postJson } from "./client";

export type ScheduleRequest = {
  ticker: string;
  interval_days?: number;
};

export const fetchMetrics = () => getJson("/metrics");
export const fetchHealth = () => getJson("/health");
export const fetchPositionsMarket = () => getJson("/positions/market");
export const fetchPositions = (status?: string) =>
  getJson(status ? `/positions?status=${encodeURIComponent(status)}` : "/positions");
export const fetchQueue = () => getJson("/queue");
export const fetchScheduleSummary = () => getJson("/schedules/summary");
export const fetchLiveEvents = (ticker: string, limit = 50) =>
  getJson(`/live/${encodeURIComponent(ticker)}/events?limit=${limit}`);
export const fetchActivity = () => getJson("/activity");
export const fetchSchedules = () => getJson("/schedules");
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

export const searchTickers = (q: string) =>
  getJson(`/search/tickers?q=${encodeURIComponent(q)}`);
