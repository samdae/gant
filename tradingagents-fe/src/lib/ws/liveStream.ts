import { BASE_URL } from "../api/client";

const toWsUrl = (baseUrl: string) => {
  if (baseUrl.startsWith("https://")) return baseUrl.replace("https://", "wss://");
  if (baseUrl.startsWith("http://")) return baseUrl.replace("http://", "ws://");
  return baseUrl;
};

export const connectLiveStream = (
  ticker: string,
  onMessage: (data: unknown) => void,
  onError?: (err: Event) => void
) => {
  const wsBase = toWsUrl(BASE_URL);
  const ws = new WebSocket(`${wsBase}/ws/analyze/${ticker}`);

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
