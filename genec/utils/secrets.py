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
