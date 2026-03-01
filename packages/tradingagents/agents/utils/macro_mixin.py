"""Shared helper to extract macro context block for agent prompts."""


def get_macro_block(state: dict) -> str:
    """Build macro context block from agent state.

    Returns empty string if no macro context available,
    so it's safe to concatenate unconditionally.
    """
    ctx = state.get("macro_context", "")
    if not ctx:
        return ""
    return (
        f"\n\n**Current Macro & Sector Context (consider this when forming your analysis):**\n"
        f"{ctx}\n"
    )
