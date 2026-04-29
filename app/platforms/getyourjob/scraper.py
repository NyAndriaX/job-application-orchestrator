from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.platforms.common.playwright_client import playwright_page

DEFAULT_FILTER = "all"
FILTER_ALIASES: dict[str, str] = {
    "toutes": "all",
    "touteslesoffres": "all",
    "free-lance": "freelance",
}
FILTER_VALUES: dict[str, str] = {
    "all": "toutes",
    "cdd": "cdd",
    "cdi": "cdi",
    "stage": "stage",
    "freelance": "freelance",
}


def normalize_filter(filter_name: str) -> str:
    normalized_filter = filter_name.strip().lower().replace(" ", "")
    return FILTER_ALIASES.get(normalized_filter, normalized_filter)


def open_homepage(filter_name: str = DEFAULT_FILTER, timeout_ms: int = 30000) -> dict:
    normalized_filter = normalize_filter(filter_name)
    if normalized_filter not in FILTER_VALUES:
        allowed_filters = ", ".join(sorted(FILTER_VALUES.keys()))
        return {
            "success": False,
            "target": "getyourjob",
            "filter": normalized_filter,
            "error": f"Unsupported filter '{normalized_filter}' for getyourjob. Allowed values: {allowed_filters}.",
        }

    with playwright_page() as (page, stealth_applied):
        try:
            response = page.goto("https://getyourjob.pro/", wait_until="domcontentloaded", timeout=timeout_ms)
            if normalized_filter != DEFAULT_FILTER:
                filter_selector_value = FILTER_VALUES[normalized_filter]
                selector = f"ul.filters .item[data-tab='{filter_selector_value}']"
                page.click(selector, timeout=10000)
                page.wait_for_timeout(600)

            page.wait_for_timeout(1500)
            return {
                "success": True,
                "target": "getyourjob",
                "filter": normalized_filter,
                "url": page.url,
                "title": page.title(),
                "user_agent": page.evaluate("() => navigator.userAgent"),
                "stealth_applied": stealth_applied,
                "status_code": response.status if response else None,
            }
        except PlaywrightTimeoutError:
            return {
                "success": False,
                "error": "Navigation timeout while opening https://getyourjob.pro/.",
            }
