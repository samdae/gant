export type Call = "BUY" | "HOLD" | "SELL";
export type Comparison = "changed" | "unchanged" | "first" | "unknown" | "unavailable";

export type ReportRound = {
  id: number;
  cycle: number | null;
  at: string;
  decision: Call | null;
};

export type PulseRow = {
  ticker: string;
  latest_at: string;
  report_count: number;
  status: Comparison;
  current: ReportRound | null;
  previous: ReportRound | null;
  reason: string | null;
};

export const callName: Record<Call, string> = { BUY: "매수", HOLD: "관망", SELL: "매도" };

export function roundLink(ticker: string, round: ReportRound) {
  return "#/reports/" + encodeURIComponent(ticker.toLowerCase()) + "?report=" + round.id;
}

const shortDate = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul", month: "numeric", day: "numeric",
});

export function roundDate(round: ReportRound) {
  const time = Date.parse(round.at);
  return Number.isFinite(time) ? shortDate.format(time) : "";
}
