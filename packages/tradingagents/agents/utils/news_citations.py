"""References explicitly cited in this trade analysis, in frozen source order."""
import re


def cited_refs(text: str, allowed: list[str]) -> list[str]:
    cited = set(re.findall(r"\[(N[1-9]\d*)\]", text))
    return [ref for ref in allowed if ref in cited]
