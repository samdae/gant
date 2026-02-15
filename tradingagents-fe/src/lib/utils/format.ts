const formatMoney = (value: number | null | undefined, currency = "$") => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value >= 0 ? "+" : "-";
  const abs = Math.abs(value);
  return `${sign}${currency}${abs.toLocaleString(undefined, {
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
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
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

export { formatMoney, formatPercent, formatDateTime, formatAgo, formatErrorMessage };
