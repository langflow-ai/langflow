#!/usr/bin/env python3
# ruff: noqa: S310, TRY003, TRY004, EM101, EM102
"""Run a route-aware IBM ACE accessibility scan with API request tracking."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, Request, async_playwright

DEFAULT_ACE_URL = "https://unpkg.com/accessibility-checker-engine@latest/ace.js"
STATIC_RESOURCE_TYPES = {"image", "media", "font"}
STATIC_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".css",
    ".map",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan loaded frontend routes with IBM ACE and record API calls.")
    parser.add_argument("--url", required=True, help="Base URL or full page URL.")
    parser.add_argument("--routes", default="", help="Comma-separated routes to scan.")
    parser.add_argument("--route", action="append", default=[], help="Route to scan. Can repeat.")
    parser.add_argument(
        "--routes-file",
        default="",
        help="Optional route manifest JSON file. Uses the selected route group when --routes/--route are omitted.",
    )
    parser.add_argument(
        "--route-group",
        default="static",
        help="Route manifest group to scan. Default: static.",
    )
    parser.add_argument(
        "--states-file",
        default="",
        help="Optional JSON file with modal/state actions to scan after route load.",
    )
    parser.add_argument(
        "--levels",
        default="violation",
        help="Comma-separated levels: violation,potentialviolation,recommendation,manual.",
    )
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--quiet-ms", type=int, default=1000)
    parser.add_argument("--out", default="a11y-scan-report.json")
    parser.add_argument("--markdown", default="", help="Optional Markdown report path.")
    parser.add_argument("--html", default="", help="Optional self-contained HTML report path.")
    parser.add_argument("--ace-url", default=DEFAULT_ACE_URL)
    parser.add_argument(
        "--browser-executable",
        default=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
        help="Optional Chrome/Chromium executable path.",
    )
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def same_origin(url: str, origin: str) -> bool:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" == origin


def is_relevant_request(request: Request, base_origin: str) -> bool:
    parsed = urlparse(request.url)
    if f"{parsed.scheme}://{parsed.netloc}" != base_origin:
        return False
    if request.resource_type in STATIC_RESOURCE_TYPES:
        return False
    return not parsed.path.lower().endswith(STATIC_EXTENSIONS)


def is_api_request(request: Request, base_origin: str) -> bool:
    parsed = urlparse(request.url)
    if f"{parsed.scheme}://{parsed.netloc}" != base_origin:
        return False
    return "/api/" in parsed.path or "/health" in parsed.path or "/config" in parsed.path


def fetch_ace_script(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def load_states_file(path_value: str) -> dict[str, list[dict[str, Any]]]:
    if not path_value:
        return {}

    with Path(path_value).open(encoding="utf-8") as file:
        raw_data = json.load(file)

    entries = raw_data.get("routes", raw_data) if isinstance(raw_data, dict) else raw_data
    if not isinstance(entries, list):
        raise ValueError("--states-file must contain a list or an object with a routes list")

    states_by_route: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("route"), str):
            raise ValueError("Each states-file route entry must have a string route")
        states = entry.get("states", [])
        if not isinstance(states, list):
            raise ValueError(f"states for route {entry['route']} must be a list")
        states_by_route[entry["route"]] = states
    return states_by_route


def load_routes_file(path_value: str, route_group: str) -> list[str]:
    if not path_value:
        return []

    with Path(path_value).open(encoding="utf-8") as file:
        manifest = json.load(file)

    if not isinstance(manifest, dict):
        raise ValueError("--routes-file must contain a JSON object")

    entries = manifest.get(route_group)
    if not isinstance(entries, list):
        raise ValueError(f"--routes-file has no list route group named {route_group!r}")

    routes: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Route group {route_group!r} entries must be objects")
        path_value = entry.get("path")
        if isinstance(path_value, str):
            routes.append(path_value)

    if not routes:
        raise ValueError(f"Route group {route_group!r} has no concrete path entries")
    return routes


def find_chromium_executable(explicit_path: str) -> str | None:
    candidates = [
        explicit_path,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


async def wait_for_settled_network(page: Page, pending: set[Request], timeout_ms: int, quiet_ms: int) -> None:
    start = time.monotonic()
    last_busy_at = time.monotonic()
    timeout = timeout_ms / 1000
    quiet = quiet_ms / 1000

    while time.monotonic() - start < timeout:
        if not pending:
            if time.monotonic() - last_busy_at >= quiet:
                return
        else:
            last_busy_at = time.monotonic()
        await page.wait_for_timeout(100)


async def evaluate_ace(page: Page, levels: list[str]) -> list[dict[str, Any]]:
    return await page.evaluate(
        """
        async (levels) => {
          const wanted = new Set(levels.map((level) => level.toLowerCase()));
          const matchesLevel = (values) => {
            if (!Array.isArray(values)) return false;
            return (
              (wanted.has("violation") && values[1] === "FAIL") ||
              (wanted.has("potentialviolation") && values[1] === "POTENTIAL") ||
              (wanted.has("recommendation") && values[1] === "RECOMMENDATION") ||
              (wanted.has("manual") && values[1] === "MANUAL")
            );
          };

          if (!window.ace?.Checker) {
            throw new Error("IBM ACE checker is not loaded");
          }

          const checker = new window.ace.Checker();
          const report = await checker.check(document);
          return report.results
            .filter((item) => matchesLevel(item.value))
            .map((item) => ({
              ruleId: item.ruleId,
              message: item.message,
              source: item.source ?? null,
              path: item.path?.dom ?? item.path?.aria ?? null,
              snippet: item.snippet ?? null,
              value: item.value,
            }));
        }
        """,
        levels,
    )


async def ensure_ace_loaded(page: Page, ace_script: str, timeout_ms: int) -> None:
    is_loaded = await page.evaluate("Boolean(window.ace?.Checker)")
    if not is_loaded:
        await page.add_script_tag(content=ace_script)
    await page.wait_for_function("Boolean(window.ace?.Checker)", timeout=timeout_ms)


async def read_visible_text(page: Page) -> str:
    return (await page.locator("body").inner_text()).strip()[:500]


async def describe_active_element(page: Page) -> dict[str, Any]:
    return await page.evaluate(
        """
        () => {
          const el = document.activeElement;
          if (!el) return {};
          return {
            tagName: el.tagName,
            id: el.id || null,
            testId: el.getAttribute("data-testid"),
            ariaLabel: el.getAttribute("aria-label"),
            text: (el.textContent || "").trim().slice(0, 120),
          };
        }
        """
    )


async def modal_diagnostics(page: Page) -> dict[str, Any]:
    return await page.evaluate(
        """
        () => {
          const dialogs = Array.from(document.querySelectorAll('[role="dialog"]')).filter((dialog) => {
            if (dialog.hidden) return false;
            const style = window.getComputedStyle(dialog);
            return style.display !== "none" && style.visibility !== "hidden";
          });
          const active = document.activeElement;
          return {
            dialogCount: dialogs.length,
            focusedWithinDialog: dialogs.some((dialog) => active && dialog.contains(active)),
            activeElement: active
              ? {
                  tagName: active.tagName,
                  id: active.id || null,
                  testId: active.getAttribute("data-testid"),
                  ariaLabel: active.getAttribute("aria-label"),
                  text: (active.textContent || "").trim().slice(0, 120),
                }
              : {},
          };
        }
        """
    )


async def run_action(page: Page, action: dict[str, Any], timeout_ms: int) -> None:
    if "click" in action:
        await page.locator(action["click"]).first.click(timeout=timeout_ms)
    elif "clickText" in action:
        await page.get_by_text(action["clickText"], exact=True).click(timeout=timeout_ms)
    elif "clickRole" in action:
        role_action = action["clickRole"]
        if not isinstance(role_action, dict):
            raise ValueError("clickRole action must be an object with role and optional name")
        await page.get_by_role(role_action["role"], name=role_action.get("name")).click(timeout=timeout_ms)
    elif "fill" in action:
        fill_action = action["fill"]
        if not isinstance(fill_action, dict):
            raise ValueError("fill action must be an object with selector and value")
        await page.locator(fill_action["selector"]).first.fill(str(fill_action.get("value", "")), timeout=timeout_ms)
    elif "press" in action:
        press_action = action["press"]
        if isinstance(press_action, dict):
            await page.locator(press_action["selector"]).first.press(press_action["key"], timeout=timeout_ms)
        else:
            await page.keyboard.press(str(press_action))
    elif "waitFor" in action:
        await page.locator(action["waitFor"]).first.wait_for(state="visible", timeout=timeout_ms)
    elif "waitForHidden" in action:
        await page.locator(action["waitForHidden"]).first.wait_for(state="hidden", timeout=timeout_ms)
    elif "waitForText" in action:
        await page.get_by_text(action["waitForText"], exact=False).first.wait_for(state="visible", timeout=timeout_ms)
    elif "wait" in action:
        await page.wait_for_timeout(int(action["wait"]))
    else:
        raise ValueError(f"Unsupported state action: {action}")


async def run_actions(
    page: Page,
    actions: list[dict[str, Any]],
    pending: set[Request],
    timeout_ms: int,
    quiet_ms: int,
) -> None:
    for action in actions:
        await run_action(page, action, timeout_ms)
        await wait_for_settled_network(page, pending, timeout_ms, quiet_ms)


async def scan_current_dom(
    page: Page,
    *,
    ace_script: str,
    levels: list[str],
    timeout_ms: int,
    route: str,
    requested_url: str,
    state_name: str,
    phase: str,
    started_at: float,
    api_requests: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await ensure_ace_loaded(page, ace_script, timeout_ms)
    issues = await evaluate_ace(page, levels)
    return {
        "route": route,
        "state": state_name,
        "phase": phase,
        "requestedUrl": requested_url,
        "finalUrl": page.url,
        "durationMs": round((time.monotonic() - started_at) * 1000),
        "apiRequests": api_requests,
        "requestFailures": failures,
        "visibleText": await read_visible_text(page),
        "diagnostics": diagnostics or {},
        "issues": issues,
    }


async def scan_route(
    browser: Any,
    ace_script: str,
    base_url: str,
    route: str,
    states: list[dict[str, Any]],
    levels: list[str],
    timeout_ms: int,
    quiet_ms: int,
) -> list[dict[str, Any]]:
    target_url = urljoin(base_url, route)
    parsed_base = urlparse(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    page = await browser.new_page()
    pending: set[Request] = set()
    requests: list[dict[str, Any]] = []
    api_requests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def on_request(request: Request) -> None:
        if is_relevant_request(request, base_origin):
            pending.add(request)
            requests.append(
                {
                    "method": request.method,
                    "url": request.url,
                    "resourceType": request.resource_type,
                }
            )
        if is_api_request(request, base_origin):
            api_requests.append({"method": request.method, "url": request.url, "status": None})

    def on_request_done(request: Request) -> None:
        pending.discard(request)

    def on_request_failed(request: Request) -> None:
        pending.discard(request)
        failures.append(
            {
                "method": request.method,
                "url": request.url,
                "failure": request.failure or "unknown",
            }
        )

    def on_response(response: Any) -> None:
        request = response.request
        for record in api_requests:
            if record["url"] == request.url and record["status"] is None:
                record["status"] = response.status
                break

    page.on("request", on_request)
    page.on("requestfinished", on_request_done)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)

    started_at = time.monotonic()
    await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
    await wait_for_settled_network(page, pending, timeout_ms, quiet_ms)
    route_results = [
        await scan_current_dom(
            page,
            ace_script=ace_script,
            levels=levels,
            timeout_ms=timeout_ms,
            route=route,
            requested_url=target_url,
            state_name="base",
            phase="loaded",
            started_at=started_at,
            api_requests=list(api_requests),
            failures=list(failures),
        )
    ]

    for state in states:
        state_name = state.get("name")
        if not isinstance(state_name, str) or not state_name:
            raise ValueError(f"State entry for {route} must include a name")
        open_actions = state.get("open", [])
        close_actions = state.get("close", [])
        if not isinstance(open_actions, list) or not isinstance(close_actions, list):
            raise ValueError(f"State {state_name} open/close actions must be lists")

        state_started_at = time.monotonic()
        api_start = len(api_requests)
        failure_start = len(failures)
        before_open_focus = await describe_active_element(page)
        await run_actions(page, open_actions, pending, timeout_ms, quiet_ms)
        open_diagnostics = await modal_diagnostics(page)
        open_diagnostics["beforeOpenActiveElement"] = before_open_focus
        route_results.append(
            await scan_current_dom(
                page,
                ace_script=ace_script,
                levels=levels,
                timeout_ms=timeout_ms,
                route=route,
                requested_url=target_url,
                state_name=state_name,
                phase="open",
                started_at=state_started_at,
                api_requests=list(api_requests[api_start:]),
                failures=list(failures[failure_start:]),
                diagnostics=open_diagnostics,
            )
        )

        if close_actions:
            await run_actions(page, close_actions, pending, timeout_ms, quiet_ms)
            close_diagnostics = await modal_diagnostics(page)
            route_results.append(
                {
                    "route": route,
                    "state": state_name,
                    "phase": "closed",
                    "requestedUrl": target_url,
                    "finalUrl": page.url,
                    "durationMs": round((time.monotonic() - state_started_at) * 1000),
                    "apiRequests": list(api_requests[api_start:]),
                    "requestFailures": list(failures[failure_start:]),
                    "visibleText": await read_visible_text(page),
                    "diagnostics": close_diagnostics,
                    "issues": [],
                }
            )

    await page.close()
    return route_results


def shortened(value: Any, limit: int = 220) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def markdown_cell(value: Any) -> str:
    text = shortened(value, 180)
    return text.replace("|", "\\|")


def result_name(result: dict[str, Any]) -> str:
    if result["state"] == "base":
        return result["route"]
    return f"{result['route']}#{result['state']}:{result['phase']}"


def rule_counts(results: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for result in results:
        counts.update(issue.get("ruleId", "unknown") for issue in result["issues"])
    return counts


def issue_rule_counts(issues: list[dict[str, Any]]) -> Counter[str]:
    return Counter(issue.get("ruleId", "unknown") for issue in issues)


def markdown_rule_table(counts: Counter[str]) -> str:
    if not counts:
        return "_No issues._"
    lines = ["| Rule | Count |", "| --- | ---: |"]
    lines.extend(f"| `{markdown_cell(rule)}` | {count} |" for rule, count in counts.most_common())
    return "\n".join(lines)


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    results = report["results"]
    lines = [
        "# Langflow Accessibility Report",
        "",
        f"- Generated: `{report['generatedAt']}`",
        f"- Base URL: `{report['url']}`",
        f"- Levels: `{', '.join(report['reportLevels'])}`",
        f"- Routes: `{', '.join(report['routes'])}`",
        f"- Total issues: `{report['totalIssues']}`",
        "",
        "## Route Summary",
        "",
        "| Route/State | Issues | API | Failures | Dialogs | Focus In Dialog |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]

    for result in results:
        diagnostics = result.get("diagnostics", {})
        lines.append(
            "| "
            f"{markdown_cell(result_name(result))} | "
            f"{len(result['issues'])} | "
            f"{len(result['apiRequests'])} | "
            f"{len(result['requestFailures'])} | "
            f"{diagnostics.get('dialogCount', '')} | "
            f"{diagnostics.get('focusedWithinDialog', '')} |"
        )

    lines.extend(["", "## Top Rules", "", markdown_rule_table(rule_counts(results)), ""])

    lines.extend(["## Findings By Route", ""])
    for result in results:
        issues = result["issues"]
        diagnostics = result.get("diagnostics", {})
        lines.extend(
            [
                f"### {result_name(result)}",
                "",
                f"- Final URL: `{result['finalUrl']}`",
                f"- Issues: `{len(issues)}`",
                f"- API requests: `{len(result['apiRequests'])}`",
                f"- Request failures: `{len(result['requestFailures'])}`",
                f"- Dialog count: `{diagnostics.get('dialogCount', '')}`",
                f"- Focus in dialog: `{diagnostics.get('focusedWithinDialog', '')}`",
                "",
                markdown_rule_table(issue_rule_counts(issues)),
                "",
            ]
        )

        for index, issue in enumerate(issues, start=1):
            lines.extend(
                [
                    f"{index}. `{issue.get('ruleId', 'unknown')}` - {shortened(issue.get('message'))}",
                    f"   - Path: `{shortened(issue.get('path'), 240)}`",
                    f"   - Source: `{shortened(issue.get('source'), 240)}`",
                    f"   - Snippet: `{shortened(issue.get('snippet'), 240)}`",
                ]
            )
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def diagnostic_value(diagnostics: dict[str, Any], key: str, default: Any) -> Any:
    value = diagnostics.get(key, default)
    return default if value in (None, "") else value


def html_rule_table(counts: Counter[str]) -> str:
    if not counts:
        return '<p class="empty">No issues.</p>'
    rows = "\n".join(
        f"<tr><td><code>{html_escape(rule)}</code></td><td>{count}</td></tr>" for rule, count in counts.most_common()
    )
    return f"<table><thead><tr><th>Rule</th><th>Count</th></tr></thead><tbody>{rows}</tbody></table>"


def write_html_report(report: dict[str, Any], output_path: Path) -> None:
    results = report["results"]
    summary_rows = []
    for result in results:
        diagnostics = result.get("diagnostics", {})
        dialog_count = diagnostic_value(diagnostics, "dialogCount", 0)
        focused_within_dialog = diagnostic_value(diagnostics, "focusedWithinDialog", "n/a")
        summary_rows.append(
            "<tr>"
            f"<td>{html_escape(result_name(result))}</td>"
            f"<td>{len(result['issues'])}</td>"
            f"<td>{len(result['apiRequests'])}</td>"
            f"<td>{len(result['requestFailures'])}</td>"
            f"<td>{html_escape(dialog_count)}</td>"
            f"<td>{html_escape(focused_within_dialog)}</td>"
            "</tr>"
        )

    grouped_results: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped_results.setdefault(result["route"], []).append(result)

    route_sections = []
    for route_index, (route, route_results) in enumerate(grouped_results.items()):
        route_issues = sum(len(result["issues"]) for result in route_results)
        route_api = sum(len(result["apiRequests"]) for result in route_results)
        route_failures = sum(len(result["requestFailures"]) for result in route_results)
        state_sections = []

        for state_index, result in enumerate(route_results):
            issues = result["issues"]
            diagnostics = result.get("diagnostics", {})
            dialog_count = diagnostic_value(diagnostics, "dialogCount", 0)
            focused_within_dialog = diagnostic_value(diagnostics, "focusedWithinDialog", "n/a")
            issue_items = []
            for index, issue in enumerate(issues, start=1):
                issue_items.append(
                    '<details class="issue">'
                    "<summary>"
                    f'<span class="issue-index">{index}</span>'
                    f"<code>{html_escape(issue.get('ruleId', 'unknown'))}</code>"
                    f"<span>{html_escape(shortened(issue.get('message'), 180))}</span>"
                    "</summary>"
                    "<dl>"
                    f"<dt>Path</dt><dd><code>{html_escape(shortened(issue.get('path'), 360))}</code></dd>"
                    f"<dt>Source</dt><dd><code>{html_escape(shortened(issue.get('source'), 360))}</code></dd>"
                    f"<dt>Snippet</dt><dd><code>{html_escape(shortened(issue.get('snippet'), 360))}</code></dd>"
                    "</dl>"
                    "</details>"
                )

            issues_html = "".join(issue_items) or '<p class="empty">No issues.</p>'
            state_open = " open" if state_index == 0 else ""
            state_sections.append(
                f'<details class="state"{state_open}>'
                "<summary>"
                f"<strong>{html_escape(result_name(result))}</strong>"
                '<span class="summary-pills">'
                f'<span class="pill danger">{len(issues)} issues</span>'
                f'<span class="pill">{len(result["apiRequests"])} API</span>'
                f'<span class="pill">{len(result["requestFailures"])} failures</span>'
                f'<span class="pill">{html_escape(dialog_count)} dialogs</span>'
                "</span>"
                "</summary>"
                '<div class="state-body">'
                f'<p class="url">{html_escape(result["finalUrl"])}</p>'
                f'<p class="muted">Focus in dialog: {html_escape(focused_within_dialog)}</p>'
                "<h4>Rules In This State</h4>"
                f"{html_rule_table(issue_rule_counts(issues))}"
                "<h4>Issues</h4>"
                f"{issues_html}"
                "</div>"
                "</details>"
            )

        route_open = " open" if route_index == 0 else ""
        route_sections.append(
            f'<details class="route"{route_open}>'
            "<summary>"
            f"<strong>{html_escape(route)}</strong>"
            '<span class="summary-pills">'
            f'<span class="pill danger">{route_issues} issues</span>'
            f'<span class="pill">{len(route_results)} states</span>'
            f'<span class="pill">{route_api} API</span>'
            f'<span class="pill">{route_failures} failures</span>'
            "</span>"
            "</summary>"
            '<div class="route-body">'
            "<h3>Route Rules</h3>"
            f"{html_rule_table(rule_counts(route_results))}"
            f"{''.join(state_sections)}"
            "</div>"
            "</details>"
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Langflow Accessibility Report</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #5f6b7a;
      --line: #d8dee6;
      --accent: #0f766e;
      --danger: #b42318;
      --code: #eef2f6;
      --soft: #eef7f6;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #101418;
        --panel: #171c22;
        --text: #edf2f7;
        --muted: #a8b3bf;
        --line: #2c3642;
        --accent: #2dd4bf;
        --danger: #f97066;
        --code: #202936;
        --soft: #102826;
      }}
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    h1, h2, h3 {{ line-height: 1.2; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    h2 {{ margin-top: 32px; }}
    h3, h4 {{ margin: 18px 0 10px; }}
    .summary {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 16px 0;
    }}
    .stats, .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .stats span, .meta span {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      color: var(--muted);
      background: color-mix(in srgb, var(--panel) 82%, var(--bg));
    }}
    .danger {{
      color: var(--danger);
      border-color: color-mix(in srgb, var(--danger) 35%, var(--line));
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      margin: 12px 0;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{
      background: var(--code);
      border-radius: 4px;
      padding: 1px 4px;
      overflow-wrap: anywhere;
    }}
    dl {{ display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: 4px 10px; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; min-width: 0; }}
    .url, .empty, .muted {{ color: var(--muted); }}
    details > summary {{
      cursor: pointer;
      list-style: none;
    }}
    details > summary::-webkit-details-marker {{ display: none; }}
    details > summary::before {{
      content: ">";
      display: inline-block;
      margin-right: 8px;
      color: var(--accent);
      transition: transform 120ms ease;
    }}
    details[open] > summary::before {{ transform: rotate(90deg); }}
    .route {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 14px 0;
      overflow: hidden;
    }}
    .route > summary {{
      align-items: center;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 18px;
      background: var(--soft);
    }}
    .route-body {{
      padding: 2px 18px 18px;
    }}
    .state {{
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 12px 0;
      background: color-mix(in srgb, var(--panel) 90%, var(--bg));
      overflow: hidden;
    }}
    .state > summary {{
      align-items: center;
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 12px 14px;
    }}
    .state-body {{
      border-top: 1px solid var(--line);
      padding: 0 14px 14px;
    }}
    .summary-pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      justify-content: flex-end;
    }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      padding: 2px 8px;
      white-space: nowrap;
    }}
    .issue {{
      border-top: 1px solid var(--line);
      padding: 10px 0;
    }}
    .issue:first-of-type {{ border-top: 0; }}
    .issue > summary {{
      display: grid;
      grid-template-columns: 32px minmax(120px, 220px) minmax(0, 1fr);
      gap: 10px;
      align-items: start;
    }}
    .issue > summary::before {{ display: none; }}
    .issue-index {{
      color: var(--muted);
      text-align: right;
    }}
    .issue dl {{
      margin: 10px 0 0 42px;
    }}
    @media (max-width: 760px) {{
      .route > summary, .state > summary {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .summary-pills {{
        justify-content: flex-start;
      }}
      .issue > summary {{
        grid-template-columns: 28px minmax(0, 1fr);
      }}
      .issue > summary span:last-child {{
        grid-column: 2;
      }}
      dl {{
        grid-template-columns: 1fr;
      }}
      .issue dl {{
        margin-left: 0;
      }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Langflow Accessibility Report</h1>
  <p class="muted">Generated {html_escape(report["generatedAt"])}</p>
  <section class="summary">
    <div class="stats">
      <span class="danger">{report["totalIssues"]} total issues</span>
      <span>{len(report["routes"])} routes</span>
      <span>levels: {html_escape(", ".join(report["reportLevels"]))}</span>
      <span>base: {html_escape(report["url"])}</span>
    </div>
  </section>
  <h2>Route Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Route/State</th><th>Issues</th><th>API</th>
        <th>Failures</th><th>Dialogs</th><th>Focus In Dialog</th>
      </tr>
    </thead>
    <tbody>{"".join(summary_rows)}</tbody>
  </table>
  <h2>Top Rules</h2>
  {html_rule_table(rule_counts(results))}
  <h2>Findings By Route</h2>
  {"".join(route_sections)}
</main>
<script>
  document.querySelectorAll("details.route").forEach((route) => {{
    route.addEventListener("toggle", () => {{
      if (!route.open) return;
      document.querySelectorAll("details.route[open]").forEach((other) => {{
        if (other !== route) other.open = false;
      }});
    }});
  }});
</script>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


async def main() -> None:
    args = parse_args()
    states_by_route = load_states_file(args.states_file)
    route_args = split_csv(args.routes) + args.route
    manifest_routes = load_routes_file(args.routes_file, args.route_group)
    routes = route_args or manifest_routes or list(states_by_route.keys()) or [urlparse(args.url).path or "/"]
    levels = split_csv(args.levels)
    ace_script = fetch_ace_script(args.ace_url)
    executable_path = find_chromium_executable(args.browser_executable)

    async with async_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": not args.headed}
        if executable_path:
            launch_options["executable_path"] = executable_path
        browser = await playwright.chromium.launch(**launch_options)
        try:
            results = []
            for route in routes:
                print(f"scan {route}")
                route_results = await scan_route(
                    browser,
                    ace_script,
                    args.url,
                    route,
                    states_by_route.get(route, []),
                    levels,
                    args.timeout_ms,
                    args.quiet_ms,
                )
                for result in route_results:
                    label = result["route"]
                    if result["state"] != "base":
                        label = f"{label}#{result['state']}:{result['phase']}"
                    print(
                        f"  {label} api={len(result['apiRequests'])} "
                        f"issues={len(result['issues'])} final={result['finalUrl']}"
                    )
                    if not result["apiRequests"] and result["phase"] != "closed":
                        print("  warn: no same-origin API/config/health requests observed")
                results.extend(route_results)
        finally:
            await browser.close()

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "url": args.url,
        "routes": routes,
        "reportLevels": levels,
        "totalIssues": sum(len(result["issues"]) for result in results),
        "results": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")

    if args.markdown:
        markdown_path = Path(args.markdown)
        write_markdown_report(report, markdown_path)
        print(f"wrote {markdown_path}")

    if args.html:
        html_path = Path(args.html)
        write_html_report(report, html_path)
        print(f"wrote {html_path}")


if __name__ == "__main__":
    asyncio.run(main())
