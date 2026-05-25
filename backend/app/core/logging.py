import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "csrf",
    "password",
    "passwd",
    "pwd",
    "refresh_token",
    "session",
    "token",
}

HEADER_PATTERN = re.compile(
    r"(?i)\b(authorization|cookie|set-cookie|x-csrf-token)\s*:\s*([^\r\n]+)"
)
ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|csrf|session|access_token|refresh_token)"
    r"\s*([=:])\s*([^\s&;,]+)"
)


def mask_secret(value: str) -> str:
    if not value:
        return value
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def redact_text(text: str) -> str:
    text = HEADER_PATTERN.sub(lambda m: f"{m.group(1)}: ***", text)
    return ASSIGNMENT_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            redacted[str(key)] = "***"
        elif isinstance(value, Mapping):
            redacted[str(key)] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[str(key)] = [
                redact_mapping(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        elif isinstance(value, str):
            redacted[str(key)] = redact_text(value)
        else:
            redacted[str(key)] = value
    return redacted
