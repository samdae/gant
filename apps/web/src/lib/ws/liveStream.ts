import { BASE_URL } from "../api/client";

const toWsUrl = (baseUrl: string) => {
  const url = new URL(baseUrl, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.href.replace(/\/$/, "");
};

export const connectLiveStream = (
  ticker: string,
  onMessage: (data: unknown) => void,
  onError?: (err: Event) => void
) => {
  const wsBase = toWsUrl(BASE_URL);
  const ws = new WebSocket(`${wsBase}/ws/analyze/${encodeURIComponent(ticker)}`);

  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      onMessage(event.data);
    }
  };

  ws.onerror = (err) => {
    if (onError) onError(err);
  };

  return ws;
};
