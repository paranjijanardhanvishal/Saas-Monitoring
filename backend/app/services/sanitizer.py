"""Sanitizer for outbound external notifications (Slack, Jira, Webhooks).

Strictly enforces the IEEE base paper privacy principles:
- Strips Bearer tokens, JWT tokens, API keys, credentials, and passwords.
- Redacts PII: Credit Card Numbers, US SSN, and sensitive financial/identity identifiers.
- Redacts raw private keys, file dumps, and token payloads.
- Binds output string length to prevent data exfiltration.
"""

from __future__ import annotations

import re
from typing import Optional

# Compiled regex patterns for high-sensitivity data
JWT_REGEX = re.compile(r"eyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]*")
BEARER_REGEX = re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{8,}")
CREDENTIAL_KEY_REGEX = re.compile(
    r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"]?[^\s,;'\"]+['\"]?"
)
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PRIVATE_KEY_REGEX = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----")


def sanitize_for_external(text: Optional[str], max_length: int = 2000) -> str:
    """Sanitize outbound text before transmission to external services (Slack, Jira)."""
    if not text:
        return ""
    clean = str(text)

    # 1. Redact Private keys
    clean = PRIVATE_KEY_REGEX.sub("[PRIVATE_KEY_REDACTED]", clean)

    # 2. Redact JWT tokens
    clean = JWT_REGEX.sub("[JWT_TOKEN_REDACTED]", clean)

    # 3. Redact Bearer tokens
    clean = BEARER_REGEX.sub("Bearer [TOKEN_REDACTED]", clean)

    # 4. Redact credential key-value pairs
    clean = CREDENTIAL_KEY_REGEX.sub(r"\1: [REDACTED]", clean)

    # 5. Redact Credit Card Numbers
    clean = CREDIT_CARD_REGEX.sub("[CARD_REDACTED]", clean)

    # 6. Redact SSNs
    clean = SSN_REGEX.sub("[SSN_REDACTED]", clean)

    return clean[:max_length]
