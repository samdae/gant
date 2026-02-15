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
export const fetchLiveEvents = (ticker: string, limit = 50) =>
  getJson(`/live/${encodeURIComponent(ticker)}/events?limit=${limit}`);
export const fetchActivity = () => getJson("/activity");
export const fetchSchedules = () => getJson("/schedules");
export const fetchScheduleCycles = (ticker: string, limit = 1, cursor?: number) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", String(cursor));
  return getJson(`/schedules/${encodeURIComponent(ticker)}/cycles?${params.toString()}`);
};

export const createSchedule = (payload: ScheduleRequest) =>
  postJson("/schedules", payload);

export const deleteSchedule = (ticker: string) =>
  deleteJson(`/schedules/${ticker}`);

export const fetchReportsByTicker = (ticker: string) =>
  getJson(`/reports?ticker=${encodeURIComponent(ticker)}`);

export const fetchPositionDetail = (id: number) =>
  getJson(`/positions/${id}`);

export const searchMemories = (query: string) =>
  getJson(`/search?query=${encodeURIComponent(query)}`);
