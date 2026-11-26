// The archive returns report prose, already filtered for public access. Only the
// submitted decision and a short extract of the final judgement reach the board.
const publicOrigin = "http://127.0.0.1:8025";
export const pulsePath = "/v4/data/report-pulse";
const minute = 60_000;
const tickerPattern = /^[A-Z0-9][A-Z0-9.-]{0,15}$/;
const decisions = new Map([
  ["BUY", "BUY"], ["매수", "BUY"], ["HOLD", "HOLD"], ["보유", "HOLD"],
  ["관망", "HOLD"], ["SELL", "SELL"], ["매도", "SELL"],
]);

function validDate(text) {
  return typeof text === "string" && /^\d{4}-\d\d-\d\dT/.test(text) && Number.isFinite(Date.parse(text));
}

function submitted(value) {
  return typeof value === "string" ? decisions.get(value.trim().toUpperCase()) ?? null : null;
}

function reasonExcerpt(raw) {
  if (typeof raw !== "string" || /^\s*(?:\{|\[["{])/.test(raw)) return null;
  const lines = raw.split(/^\s*\x60{3}/m, 1)[0].split(/\r?\n/)
    .map(line => line.replace(/^\s*(?:#{1,6}\s+|[-*•]\s+|>\s*)/, "")
      .replace(/\*\*|__|\x60/g, "").trim())
    .filter(line => line && !/^[{[|]|^[-=]+$|https?:\/\/|<[^>]+>/.test(line));
  const label = /^(?:(?:핵심|주요|판단|투자|매매|결정)\s*)?(?:근거|판단\s*이유|결정\s*이유|rationale|reasoning)\s*(?:[:：]\s*|$)/i;
  const index = lines.findIndex(line => label.test(line));
  let passage;
  if (index >= 0) {
    passage = lines[index].replace(label, "").trim() || lines[index + 1];
  } else {
    // Some reports have an unlabelled rationale immediately after their trade
    // recommendation. Skip the recommendation, objectives, and execution rules.
    const opening = lines[0]?.match(/.+?(?:[.!?](?=\s|$)|$)/gu) || [];
    const isReason = line =>
      !/^[^.!?]{1,25}[:：]|^(?:실행|가격|포지션|보유자|신규|미보유자|5거래일 상승 확률)/.test(line)
      && /[가-힣].*(?:근거|때문|부담|개선|반면|늘었|둔화|악화|감소|불확실|밑돌|웃돌|뒷받침|견조|약세)/.test(line);
    const start = opening.findIndex((sentence, i) => i > 0 && isReason(sentence.trim()));
    passage = start >= 0 ? opening.slice(start).join("").trim() : lines.slice(1).find(isReason);
  }
  if (!passage || !/[가-힣a-z]{2}/i.test(passage)) return null;
  // Preserve clauses, negation and decimal prices. Mark an omitted tail.
  const sentences = passage.match(/.+?(?:[.!?](?=\s|$)|$)/gu) || [];
  const firstTwo = sentences.slice(0, 2).join("").trim();
  if (firstTwo.length <= 200) return firstTwo || null;
  if (sentences[0].trim().length <= 200) return sentences[0].trim();
  return passage.slice(0, 199).replace(/\s+\S*$/, "").trimEnd() + "…";
}

function compactRound(row, ticker) {
  if (!row || row.ticker !== ticker || !Number.isSafeInteger(row.id) || row.id <= 0 || !validDate(row.created_at)) {
    throw Error("Unverified report identity");
  }
  return { id: row.id, cycle: Number.isSafeInteger(row.scheduled_cycle) ? row.scheduled_cycle : null,
    at: row.created_at, decision: submitted(row.stored_decision_position) };
}

function projectPair(summary, reports) {
  const ticker = summary.ticker;
  if (!Array.isArray(reports) || reports.length !== Math.min(summary.report_count, 2)) {
    throw Error("Report directory and history do not agree");
  }
  const current = compactRound(reports[0], ticker);
  const previous = reports.length > 1 ? compactRound(reports[1], ticker) : null;
  // The history endpoint orders published reports by descending database ID.
  // Reject independently cached responses from different publication times.
  if (current.at !== summary.latest_at
      || (previous && (previous.id >= current.id || Date.parse(previous.at) > Date.parse(current.at)))
      || submitted(summary.stored_decision_position) !== current.decision) {
    throw Error("Unverified report order");
  }
  let status = "first";
  if (!current.decision || (previous && !previous.decision)) status = "unknown";
  else if (previous) status = previous.decision === current.decision ? "unchanged" : "changed";
  return { ticker, report_count: summary.report_count, latest_at: summary.latest_at, status,
    current, previous, reason: reasonExcerpt(reports[0].final_trade_decision) };
}

async function readPublic(path, signal) {
  const response = await fetch(publicOrigin + path, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(4000)]),
    redirect: "error", headers: { Accept: "application/json" },
  });
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
    await response.body?.cancel();
    throw Error("Public report reader is unavailable");
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of response.body) {
    size += chunk.length;
    if (size > 8 * 1024 * 1024) throw Error("Oversized public read");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export function createPulseReader({ read = readPublic, now = Date.now } = {}) {
  let pairs = new Map(), snapshot, expires = 0, pending;

  async function refresh() {
    const signal = AbortSignal.timeout(14000);
    const directory = await read("/workspace-api/reports/tickers", signal);
    if (!Array.isArray(directory) || directory.length > 2000) throw Error("Invalid report directory");
    const seen = new Set();
    for (const summary of directory) {
      if (!summary || typeof summary.ticker !== "string" || !tickerPattern.test(summary.ticker)
          || seen.has(summary.ticker) || !Number.isSafeInteger(summary.report_count)
          || summary.report_count < 1 || !validDate(summary.latest_at)) throw Error("Invalid report directory");
      seen.add(summary.ticker);
    }
    const next = new Map(), rows = new Array(directory.length);
    let index = 0;
    async function worker() {
      while (index < directory.length) {
        const i = index++;
        const summary = directory[i];
        const { ticker, report_count, latest_at } = summary;
        const signature = JSON.stringify([report_count, latest_at, summary.latest_cycle, summary.stored_decision_position]);
        const prior = pairs.get(ticker);
        if (prior?.signature === signature && now() < prior.expires) {
          next.set(ticker, prior);
          rows[i] = prior.row;
          continue;
        }
        try {
          signal.throwIfAborted();
          const reports = await read("/workspace-api/reports?ticker=" + encodeURIComponent(ticker) + "&limit=2", signal);
          const row = projectPair(summary, reports);
          rows[i] = row;
          next.set(ticker, { signature, expires: now() + 4 * 60 * minute, row });
        } catch {
          rows[i] = { ticker, report_count, latest_at, status: "unavailable", current: null, previous: null, reason: null };
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(4, directory.length) }, worker));
    pairs = next;
    snapshot = { as_of: new Date(now()).toISOString(), rows };
    expires = now() + (rows.some(row => row.status === "unavailable") ? 45_000 : 5 * minute);
    return snapshot;
  }

  return async function pulse() {
    if (now() < expires) {
      if (!snapshot) throw Error("Public report reader is unavailable");
      return snapshot;
    }
    if (!pending) pending = refresh().catch(error => {
      snapshot = null;
      expires = now() + 15_000;
      throw error;
    }).finally(() => { pending = undefined; });
    return pending;
  };
}

export function pulseMiddleware(read = createPulseReader()) {
  return async function servePulse(req, res, next) {
    if (req.url?.split("?", 1)[0] !== pulsePath) { next(); return; }
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405, { Allow: "GET, HEAD" }); res.end(); return;
    }
    if (req.url !== pulsePath) { res.writeHead(400); res.end(); return; }
    try {
      const pulse = await read();
      const partial = pulse.rows.some(row => row.status === "unavailable");
      const body = JSON.stringify(pulse);
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": partial ? "no-store" : "public, max-age=60", "Content-Length": Buffer.byteLength(body) });
      res.end(req.method === "HEAD" ? undefined : body);
    } catch {
      res.writeHead(503, { "Retry-After": "15" }); res.end();
    }
  };
}
