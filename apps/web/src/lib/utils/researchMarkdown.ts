import { Marked, marked } from "marked";
import DOMPurify from "dompurify";
import { isForecastLab } from "../workspace";

const labels = new Map(
  Object.entries({
    action: "판단",
    conviction: "확신도",
    allocation_pct: "제안 비중",
    forecast_5s: "5거래일 전망",
    p_up: "상승 확률",
    probability: "상승 확률",
    market_data_date: "시세 기준일",
    judge_model: "판정 모델",
    rationale: "판단 근거",
    analysis_accuracy: "분석 평가",
    rag_contribution: "경험 활용 평가",
    allocation_accuracy: "배분 평가",
    key_lessons: "교훈",
    summary: "요약",
    reflection_content: "회고",
    analysis_content: "분석 내용",
    strategy_update: "전략 변경",
    stop_loss: "손절 기준",
    target: "목표 가격",
    shares: "수량",
    total_return_pct: "총 수익률",
  }),
);
const narrativeFields = new Set([
  "content",
  "final_response",
  "output",
  "text",
]);
const decisions = new Map(
  Object.entries({
    BUY: "매수",
    SELL: "매도",
    HOLD: "보유",
    HIGH: "높음",
    MEDIUM: "중간",
    LOW: "낮음",
  }),
);

// CommonMark will not close an emphasis delimiter between punctuation and a Korean particle.
const reportMarkdown = new Marked({
  extensions: [
    {
      name: "koreanStrong",
      level: "inline",
      start(source) {
        return source.indexOf("**");
      },
      tokenizer(source) {
        const match = /^\*\*([^*\s](?:[^*\n]*?[^*\s])?)\*\*(?=[가-힣])/u.exec(
          source,
        );
        if (match)
          return {
            type: "koreanStrong",
            raw: match[0],
            tokens: this.lexer.inlineTokens(match[1]),
          };
      },
      renderer(token) {
        return (
          "<strong>" + this.parser.parseInline(token.tokens ?? []) + "</strong>"
        );
      },
    },
  ],
});

function markdown(text: string) {
  return marked.parse(text, { async: false }) as string;
}

function fromJson(raw: string, depth: number): string {
  try {
    return renderValue(JSON.parse(raw), depth + 1);
  } catch {
    return "";
  }
}

function renderValue(value: unknown, depth: number, key = ""): string {
  if (depth > 12 || value == null) return "";
  if (typeof value === "string") {
    if (key === "action" || key === "conviction") {
      const decision = decisions.get(value.trim().toUpperCase());
      if (decision) return decision;
    }
    return narrative(value, depth);
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    if (key === "p_up" || key === "probability") {
      return value >= 0 && value <= 1
        ? Number((value * 100).toFixed(2)) + "%"
        : "";
    }
    return key === "allocation_pct" || key === "total_return_pct"
      ? value + "%"
      : String(value);
  }
  if (Array.isArray(value))
    return value.map((item) => renderValue(item, depth + 1, key)).join("\n");
  if (typeof value !== "object") return "";

  const obj = value as Record<string, unknown>;
  if (
    ["tool", "system", "developer", "user"].includes(String(obj.role)) ||
    /tool|function|call|metadata|reasoning/.test(
      String(obj.type ?? "").toLowerCase(),
    )
  )
    return "";
  const sections: string[] = [];
  for (const [field, v] of Object.entries(obj)) {
    const label = labels.get(field);
    if (!label && !narrativeFields.has(field)) continue;
    const html = renderValue(v, depth + 1, field);
    if (html)
      sections.push(
        label
          ? "<dl><dt><strong>" +
              label +
              "</strong></dt><dd>" +
              html +
              "</dd></dl>"
          : html,
      );
  }
  return sections.join("\n");
}

const startsJson = /^\s*(?:\{|\[\s*(?:[{"\[]|\]|$))/;
const fence = /^\s*(`{3,}|~{3,})\s*([^\s]*)[^\n]*$/;

function narrative(source: string, depth: number): string {
  if (depth > 12) return "";
  const text = source.trim();
  if (!text) return "";
  if (startsJson.test(text) || text.startsWith('"')) {
    try {
      return renderValue(JSON.parse(text), depth + 1);
    } catch {
      /* Mixed prose and structured blocks are processed below. */
    }
  }
  const lines = text.split(/\r?\n/);
  const html: string[] = [];
  let prose: string[] = [];
  function flush() {
    if (prose.length)
      html.push(
        reportMarkdown.parse(prose.join("\n"), { async: false }) as string,
      );
    prose = [];
  }
  for (let i = 0; i < lines.length; ) {
    const line = lines[i++];
    const opening = fence.exec(line);
    if (opening) {
      flush();
      const block: string[] = [];
      const close = new RegExp(
        "^\\s*" + opening[1][0] + "{" + opening[1].length + ",}\\s*$",
      );
      while (i < lines.length && !close.test(lines[i])) block.push(lines[i++]);
      if (i < lines.length) i++;
      const language = opening[2].toLowerCase();
      const body = block.join("\n");
      if (language === "md" || language === "markdown")
        html.push(narrative(body, depth + 1));
      else if (["", "json", "strategy_json"].includes(language))
        html.push(fromJson(body, depth));
      continue;
    }
    if (startsJson.test(line)) {
      flush();
      const block = [line];
      // Recognize whole nested JSON objects without letting inner closing braces expose the remainder.
      const balance = (s: string) => {
        const structural = s.replace(/"(?:\\.|[^"\\])*"/g, "");
        return (
          (structural.match(/[[{]/g)?.length ?? 0) -
          (structural.match(/[\]}]/g)?.length ?? 0)
        );
      };
      let remaining = balance(line);
      while (
        remaining > 0 &&
        i < lines.length &&
        lines[i].trim() &&
        !fence.test(lines[i])
      ) {
        remaining += balance(lines[i]);
        block.push(lines[i++]);
      }
      html.push(fromJson(block.join("\n"), depth));
      continue;
    }
    prose.push(line);
  }
  flush();
  return html.join("\n").trim();
}

// This is intermediate HTML. Only renderNarrative's sanitized result may enter the DOM.
export function formatResearchNarrative(text: string) {
  return narrative(text, 0);
}

export function renderNarrative(
  text: string | null | undefined,
  empty: string,
): string {
  const html = text
    ? isForecastLab
      ? formatResearchNarrative(text)
      : markdown(text)
    : "";
  if (!html)
    return (
      "<em>" +
      empty.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") +
      "</em>"
    );
  return isForecastLab
    ? DOMPurify.sanitize(html, { FORBID_TAGS: ["img", "iframe"] })
    : DOMPurify.sanitize(html);
}
