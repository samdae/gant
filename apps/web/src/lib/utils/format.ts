const formatMoney = (value: number | null | undefined, currency = "$") => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value >= 0 ? "+" : "-";
  const abs = Math.abs(value);
  return `${sign}${currency}${abs.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const formatMoneyPlain = (value: number | null | undefined, currency = "$") => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const abs = Math.abs(value);
  return `${currency}${abs.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const formatPercent = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value >= 0 ? "+" : "-";
  const abs = Math.abs(value);
  return `${sign}${abs.toFixed(2)}%`;
};

const formatDateTime = (iso?: string | null) => {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
};

const formatAgo = (iso?: string | null) => {
  if (!iso) return "-";
  const date = new Date(iso);
  const diff = Date.now() - date.getTime();
  if (Number.isNaN(diff)) return iso;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "방금 전";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
};

const formatErrorMessage = (error: unknown, fallback = "Request failed.") => {
  if (error instanceof Error) {
    const message = error.message || fallback;
    if (/failed to fetch/i.test(message)) {
      return "Network error. Please try again.";
    }
    if (/(unauthorized|forbidden|401|403)/i.test(message)) {
      return "Authorization required. Please sign in again.";
    }
    if (/(not found|404)/i.test(message)) {
      return "Requested data was not found.";
    }
    return message;
  }
  return fallback;
};

const formatAmount = (value: number | null | undefined, ticker: string) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const isKRW = ticker.toUpperCase().endsWith(".KS") || ticker.toUpperCase().endsWith(".KQ");
  const sym = isKRW ? "₩" : "$";
  const digits = isKRW ? 0 : 2;
  return `${sym}${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
};

const formatSignedAmount = (value: number | null | undefined, ticker: string) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${formatAmount(Math.abs(value), ticker)}`;
};

export { formatMoney, formatMoneyPlain, formatPercent, formatDateTime, formatAgo, formatErrorMessage, formatAmount, formatSignedAmount };
