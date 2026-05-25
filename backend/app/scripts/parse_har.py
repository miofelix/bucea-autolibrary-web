from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

SENSITIVE_KEYWORDS = {
    "access_token",
    "answer",
    "authorization",
    "captcha",
    "code",
    "cookie",
    "csrf",
    "jsessionid",
    "password",
    "passwd",
    "pwd",
    "refresh_token",
    "session",
    "token",
    "account",
    "student",
    "user_id",
    "userid",
    "username",
}

TEXT_MIME_HINTS = ("json", "text", "html", "xml", "javascript", "x-www-form-urlencoded")
STATIC_EXTENSIONS = (
    ".css",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".js",
    ".map",
    ".png",
    ".svg",
    ".ttf",
    ".woff",
    ".woff2",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(keyword in key_lower for keyword in SENSITIVE_KEYWORDS)


def redact_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if not isinstance(value, str):
        return "***"
    if len(value) <= 4:
        return "***"
    return "***"


def safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if not isinstance(value, str):
        return str(type(value).__name__)
    if len(value) > 120:
        return value[:117] + "..."
    return value


def redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "***" if is_sensitive_key(str(key)) else redact_json(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_json(item) for item in value[:20]]
    return value


def redact_header_pairs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redacted = []
    for item in items:
        name = str(item.get("name", ""))
        value = item.get("value", "")
        redacted.append(
            {
                "name": name,
                "value": "***" if is_sensitive_key(name) else redact_scalar(value),
            }
        )
    return redacted


def redact_param_pairs(
    items: list[dict[str, Any]],
    extra_sensitive_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    extra_sensitive_names = extra_sensitive_names or set()
    redacted = []
    for item in items:
        name = str(item.get("name", ""))
        value = item.get("value", "")
        redacted.append(
            {
                "name": name,
                "value": "***"
                if is_sensitive_key(name) or name.lower() in extra_sensitive_names
                else safe_scalar(value),
            }
        )
    return redacted


def redact_text(text: str) -> str:
    text = re.sub(
        r"(?i)\b(authorization|cookie|set-cookie|x-csrf-token)\s*:\s*[^\r\n]+",
        lambda m: f"{m.group(1)}: ***",
        text,
    )
    text = re.sub(
        r"(?i)\b(password|passwd|pwd|token|csrf|session|captcha|answer|code)"
        r"\s*([=:])\s*([^&\s;,<]+)",
        lambda m: f"{m.group(1)}{m.group(2)}***",
        text,
    )
    return text


def safe_json_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def summarize_body(
    post_data: dict[str, Any] | None,
    path: str = "",
) -> dict[str, Any] | None:
    if not post_data:
        return None
    mime_type = post_data.get("mimeType", "")
    params = post_data.get("params") or []
    text = post_data.get("text") or ""
    summary: dict[str, Any] = {"mimeType": mime_type}
    extra_sensitive_names = {"id"} if "cancel" in path.lower() else set()
    if params:
        summary["params"] = redact_param_pairs(params, extra_sensitive_names)
    elif text:
        parsed = safe_json_loads(text)
        if parsed is not None:
            summary["json"] = redact_json(parsed)
        else:
            parsed_pairs = parse_qsl(text, keep_blank_values=True)
            if parsed_pairs:
                summary["form"] = [
                    {
                        "name": name,
                        "value": "***"
                        if is_sensitive_key(name) or name.lower() in extra_sensitive_names
                        else safe_scalar(value),
                    }
                    for name, value in parsed_pairs
                ]
            else:
                summary["text_sample"] = redact_text(text[:800])
    return summary


def summarize_response(content: dict[str, Any]) -> dict[str, Any]:
    mime_type = content.get("mimeType", "")
    text = content.get("text") or ""
    summary: dict[str, Any] = {
        "mimeType": mime_type,
        "size": content.get("size"),
    }
    if not text:
        return summary
    parsed = safe_json_loads(text)
    if parsed is not None:
        summary["json_sample"] = redact_json(parsed)
    return summary


def classify(entry: dict[str, Any]) -> list[str]:
    request = entry.get("request", {})
    url = request.get("url", "")
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    if path.endswith(STATIC_EXTENSIONS) or "/assets/" in path:
        return ["static"]
    tags: list[str] = []

    if path.endswith("/login") or path.endswith("/auth/signin"):
        tags.append("login")
    if path.endswith("/auth/createcaptcha"):
        tags.append("captcha")
    if path.endswith("/freebook/ajaxgetrooms"):
        tags.append("room")
    if path.endswith("/freebook/ajaxsearch"):
        tags.append("seat")
    if path.endswith("/freebook/ajaxgettime") or path.endswith("/freebook/ajaxgetendtime"):
        tags.append("seat_time")
    if path.endswith("/selfres"):
        tags.append("reserve")
    if path.endswith("/history"):
        tags.append("history")
    if path.endswith("/logout"):
        tags.append("logout")

    lower_url = url.lower()
    for tag, keywords in {
        "checkin": ("checkin", "check-in"),
        "renew": ("renew", "extend"),
        "cancel": ("cancel", "checkout"),
        "logout": ("logout", "signout"),
    }.items():
        if tag not in tags and any(keyword in lower_url for keyword in keywords):
            tags.append(tag)
    return tags or ["other"]


def request_summary(entry: dict[str, Any], har_file: Path) -> dict[str, Any]:
    request = entry.get("request", {})
    response = entry.get("response", {})
    parsed_url = urlparse(request.get("url", ""))
    query_pairs = [{"name": key, "value": value} for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)]
    return {
        "source": str(har_file.relative_to(project_root())),
        "startedDateTime": entry.get("startedDateTime"),
        "method": request.get("method", ""),
        "url": f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}",
        "scheme": parsed_url.scheme,
        "domain": parsed_url.netloc,
        "path": parsed_url.path or "/",
        "query": redact_param_pairs(query_pairs),
        "requestHeaders": redact_header_pairs(request.get("headers") or []),
        "cookies": redact_header_pairs(request.get("cookies") or []),
        "body": summarize_body(request.get("postData"), parsed_url.path or "/"),
        "response": {
            "status": response.get("status"),
            "statusText": response.get("statusText"),
            "headers": redact_header_pairs(response.get("headers") or []),
            "content": summarize_response(response.get("content") or {}),
            "redirectURL": response.get("redirectURL") or "",
        },
        "tags": classify(entry),
    }


def load_entries(har_files: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for har_file in har_files:
        with har_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        for entry in data.get("log", {}).get("entries", []):
            entries.append(request_summary(entry, har_file))
    return entries


def endpoint_groups(entries: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        groups[(entry["scheme"], entry["domain"], entry["method"], entry["path"])].append(entry)
    return dict(groups)


def md_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def render_raw(entries: list[dict[str, Any]]) -> str:
    groups = endpoint_groups(entries)
    tag_counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        for tag in entry["tags"]:
            tag_counts[tag] += 1

    lines = [
        "# API Discovery Raw",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- HAR requests parsed: {len(entries)}",
        f"- Endpoint groups: {len(groups)}",
        f"- Tags: {dict(sorted(tag_counts.items()))}",
        "",
        "## Endpoint Groups",
        "",
    ]
    for (scheme, domain, method, path), grouped_entries in sorted(groups.items()):
        first = grouped_entries[0]
        tags = sorted({tag for entry in grouped_entries for tag in entry["tags"]})
        statuses = sorted({str(entry["response"]["status"]) for entry in grouped_entries})
        lines.extend(
            [
                f"### {method} {scheme}://{domain}{path}",
                "",
                f"- Count: {len(grouped_entries)}",
                f"- Tags: {', '.join(tags)}",
                f"- Statuses: {', '.join(statuses)}",
                f"- Evidence: {first['source']}",
                "- Sample request:",
                "",
                "```json",
                md_json(
                    {
                        "method": first["method"],
                        "url": first["url"],
                        "query": first["query"],
                        "requestHeaders": first["requestHeaders"],
                        "cookies": first["cookies"],
                        "body": first["body"],
                    }
                ),
                "```",
                "",
                "- Sample response:",
                "",
                "```json",
                md_json(first["response"]),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def status_for_tag(tag: str) -> str:
    if tag in {"reserve", "checkin", "renew", "cancel"}:
        return "needs_user_confirmation"
    if tag in {"login", "captcha", "area", "room", "seat", "seat_time", "history", "logout"}:
        return "needs_user_confirmation"
    return "unknown"


def risk_for_tag(tag: str) -> str:
    if tag in {"reserve", "checkin", "renew", "cancel"}:
        return "mutation"
    if tag in {"login", "captcha", "logout"}:
        return "sensitive"
    return "read_only"


def render_snapshot(entries: list[dict[str, Any]]) -> str:
    tags: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        for tag in entry["tags"]:
            if tag != "other":
                tags[tag].append(entry)

    lines = [
        "<!-- HAR_DISCOVERY_START -->",
        "## HAR Discovery Snapshot",
        "",
        f"- Last generated: {datetime.now(timezone.utc).isoformat()}",
        f"- HAR requests parsed: {len(entries)}",
        "- Note: This section is generated from redacted HAR summaries. Sensitive values are masked.",
        "",
    ]
    for tag in sorted(tags):
        if tag == "static":
            continue
        grouped = endpoint_groups(tags[tag])
        lines.extend(
            [
                f"### {tag}",
                "",
                f"- Status: {status_for_tag(tag)}",
                f"- Risk: {risk_for_tag(tag)}",
                f"- Evidence count: {len(tags[tag])}",
                "- Candidate endpoints:",
            ]
        )
        for (scheme, domain, method, path), grouped_entries in sorted(grouped.items()):
            statuses = sorted({str(entry["response"]["status"]) for entry in grouped_entries})
            lines.append(
                f"  - `{method} {scheme}://{domain}{path}`; "
                f"count={len(grouped_entries)}; statuses={','.join(statuses)}"
            )
        lines.append("")
    lines.append("<!-- HAR_DISCOVERY_END -->")
    return "\n".join(lines)


def update_api_discovery(api_file: Path, snapshot: str) -> None:
    if not api_file.exists():
        api_file.write_text(snapshot + "\n", encoding="utf-8")
        return
    content = api_file.read_text(encoding="utf-8")
    pattern = re.compile(
        r"<!-- HAR_DISCOVERY_START -->.*?<!-- HAR_DISCOVERY_END -->",
        flags=re.DOTALL,
    )
    if pattern.search(content):
        content = pattern.sub(snapshot, content)
    else:
        content = content.rstrip() + "\n\n" + snapshot + "\n"
    api_file.write_text(content, encoding="utf-8")


def main() -> int:
    root = project_root()
    har_dir = root / "docs" / "har"
    har_files = sorted(har_dir.glob("*.har"))
    if not har_files:
        raise SystemExit("No HAR files found in docs/har")

    entries = load_entries(har_files)
    raw_file = root / "docs" / "API_DISCOVERY_RAW.md"
    raw_file.write_text(render_raw(entries), encoding="utf-8")
    update_api_discovery(root / "docs" / "API_DISCOVERY.md", render_snapshot(entries))

    print(f"Parsed {len(entries)} requests from {len(har_files)} HAR file(s)")
    print(f"Wrote {raw_file.relative_to(root)}")
    print("Updated docs/API_DISCOVERY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
