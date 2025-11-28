"""
Temporary hardcoded secrets (INSECURE).

Place your Anthropic API key here only as a short-term measure. DO NOT commit
this file to version control with a real key. Remove or rotate the key before
pushing or sharing the repository.

Usage:
    from genec.utils.secrets import get_anthropic_api_key
    key = get_anthropic_api_key()

Note: Prefer environment variables, OS keychain, or CI secret stores.
"""

ANTHROPIC_API_KEY = "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" 
\
""
def get_anthropic_api_key():
    """Return the hardcoded Anthropic API key or raise if it looks unset.

    This helper simply centralizes the hardcoded value and provides a
    guardrail so accidental empty/default values are noticed quickly.
    """
    if not ANTHROPIC_API_KEY or "REPLACE" in ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Anthropic API key not set in genec/utils/secrets.py; replace the placeholder"
        )
    return ANTHROPIC_API_KEY
