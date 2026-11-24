export const isForecastLab = import.meta.env.VITE_FORECAST_LAB === "1";
export const isPublicViewer = isForecastLab && typeof document !== "undefined" &&
  document.querySelector('meta[name="forecast-console-access"]')?.getAttribute("content") === "public-readonly";
