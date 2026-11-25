export type DateRange = { from: string; to: string };

export const marketOptions = [
  { value: "", label: "전체 시장" },
  { value: "us", label: "미국" },
  { value: "kr", label: "한국" },
];

export const rangeLabel = ({ from, to }: DateRange) =>
  from && to
    ? from === to
      ? from
      : from + " ~ " + to
    : from
      ? from + " 이후"
      : to
        ? to + " 이전"
        : "전체 기간";

function utcDay(year: number, month: number, day: number): Date {
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  return date;
}

function iso(date: Date): string {
  if (date.getUTCFullYear() < 1) return "0001-01-01";
  if (date.getUTCFullYear() > 9999) return "9999-12-31";
  return date.toISOString().slice(0, 10);
}

export function validDay(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number);
  return y >= 1 && iso(utcDay(y, m, d)) === value;
}

export const currentDay = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(
    new Date(),
  );
export function monthDays(value: string) {
  const [year, month] = value.split("-").map(Number);
  const offset = utcDay(year, month, 1).getUTCDay();
  const count = utcDay(year, month + 1, 0).getUTCDate();
  return {
    year,
    month,
    offset,
    days: Array.from({ length: count }, (_, i) =>
      iso(utcDay(year, month, i + 1)),
    ),
  };
}
export const dateName = (value: string) => {
  const [y, m, d] = value.split("-").map(Number);
  return y + "년 " + m + "월 " + d + "일";
};
export function shiftDays(value: string, distance: number) {
  const [y, m, d] = value.split("-").map(Number);
  return iso(utcDay(y, m, d + distance));
}
export function shiftMonths(value: string, distance: number) {
  const [y, m, d] = value.split("-").map(Number);
  const next = utcDay(y, m + distance, 1);
  if (next.getUTCFullYear() < 1 || next.getUTCFullYear() > 9999)
    return iso(next);
  return iso(
    utcDay(
      next.getUTCFullYear(),
      next.getUTCMonth() + 1,
      Math.min(d, utcDay(y, m + distance + 1, 0).getUTCDate()),
    ),
  );
}

export function readResearchFilters(query: string) {
  const params = new URLSearchParams(query);
  const market = params.get("market") || "";
  const from = params.get("from_date") || "";
  const to = params.get("to_date") || "";
  return {
    market: marketOptions.some((option) => option.value === market)
      ? market
      : "",
    from: validDay(from) ? from : "",
    to: validDay(to) ? to : "",
  };
}
