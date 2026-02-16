"""Model name validators.

Antigravity accepts any model name (mapped internally),
so validation always returns True.
"""


def validate_model(provider: str, model: str) -> bool:
    """Check if model name is valid for the given provider.

    Antigravity accepts any model — mapping is handled internally.
    """
    return True
