"""Isolated invocation of the original official Codex client."""

import json
import sys

from .bounded_process import bounded_run


def invoke_codex(model, prompt, timeout):
    command = [sys.executable, "-m", "tradingagents.forecast_lab.model_runner"]
    result = json.loads(
        bounded_run(
            command,
            json.dumps({"model": model, "prompt": prompt}),
            timeout,
            "Official Codex turn",
        )
    )
    if result.get("error"):
        raise RuntimeError("Official Codex invocation failed: " + result["error"])
    return result["content"]


def main():
    # Do not spawn the SDK app-server before the parent assigns this subprocess
    # to its Windows job (or starts its POSIX group) and releases the stdin gate.
    spec = json.load(sys.stdin)
    from tradingagents.llm_clients.codex_client import ChatCodex

    try:
        result = {
            "content": ChatCodex(model=spec["model"]).invoke(spec["prompt"]).content
        }
    except Exception as exc:  # noqa: BLE001 -- serialize SDK failures without credentials or model input
        result = {"error": type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
