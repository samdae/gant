const kst = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
export function operationTime(value?: string | null) {
  return value && Number.isFinite(Date.parse(value)) ? kst.format(new Date(value)) : "—";
}
export function operationState(value?: string) {
  const labels: Record<string, string> = {
    pending: "대기",
    queued: "대기",
    running: "실행 중",
    started: "시작",
    done: "완료",
    completed: "완료",
    success: "완료",
    failed: "실패",
    error: "오류",
    skipped: "건너뜀",
    cancelled: "취소",
  };
  const status = typeof value === "string" ? value.trim().toLowerCase() : "";
  return Object.prototype.hasOwnProperty.call(labels, status) ? labels[status] : "미확인";
}
