import assert from "node:assert/strict";
import { test } from "node:test";
import { createServer } from "vite";

test("research reports show narrative and decision fields while excluding machine output", async () => {
  const server = await createServer({
    configFile: false,
    server: { middlewareMode: true },
    logLevel: "silent",
  });
  try {
    const { formatResearchNarrative: render } = await server.ssrLoadModule(
      "/src/lib/utils/researchMarkdown.ts",
    );
    assert.match(
      render("영업이익률은 **32.0%→33.4%**로, 추정치는 **48%**로 조정"),
      /<strong>32\.0%→33\.4%<\/strong>로, 추정치는 <strong>48%<\/strong>로/,
    );
    assert.match(render("**49%**로 보고했다."), /<strong>49%<\/strong>로/);
    assert.match(render("`**48%**로`"), /<code>\*\*48%\*\*로<\/code>/);
    const secret = "PRIVATE_TOOL_CONTENT";
    const envelope = {
      content: [
        {
          type: "output_text",
          text: JSON.stringify({
            rationale: "가격은 **상승**했습니다.",
            forecast_5s: { p_up: 0.77 },
            action: "BUY",
          }),
        },
        { type: "function_call_output", text: secret },
        { role: "tool", content: secret },
      ],
      calls: [{ content: secret }],
      provider_metadata: { text: secret },
      metadata: { text: secret },
      additional_kwargs: { content: secret },
      usage: { text: secret },
    };
    for (const input of [
      JSON.stringify(envelope),
      JSON.stringify(JSON.stringify(envelope)),
      ["```json", JSON.stringify(envelope), "```"].join("\n"),
    ]) {
      const html = render(input);
      assert.match(html, /<strong>상승<\/strong>/);
      assert.match(html, /상승 확률/);
      assert.match(html, /77%/);
      assert.match(html, /매수/);
      assert.doesNotMatch(
        html,
        /PRIVATE_TOOL_CONTENT|calls|usage|metadata|additional_kwargs|function_call|forecast_5s|p_up|\*\*|[{}]/,
      );
    }
    const mixed = [
      "## 검토",
      "",
      "```json",
      '{"calls":[broken,' + secret,
      "```",
      "",
      "```python",
      'print("' + secret + '")',
      "```",
      "",
      "결론은 *보류*입니다.",
    ].join("\n");
    assert.match(render(mixed), /<h2>검토<\/h2>/);
    assert.match(render(mixed), /<em>보류<\/em>/);
    assert.doesNotMatch(
      render(mixed),
      /calls|PRIVATE_TOOL_CONTENT|python|print/,
    );
    const bare =
      "앞 문단\n\n" +
      JSON.stringify(
        { calls: [{ args: secret }], metadata: { text: secret } },
        null,
        2,
      ) +
      "\n\n뒤 문단";
    assert.match(render(bare), /뒤 문단/);
    assert.doesNotMatch(
      render(bare),
      /calls|metadata|PRIVATE_TOOL_CONTENT|[{}]/,
    );
    assert.equal(render('{"calls":[broken'), "");
    assert.equal(render(JSON.stringify({ calls: [secret] })), "");
  } finally {
    await server.close();
  }
});
