import importlib
import shutil
from dataclasses import dataclass

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def apply_stealth(page: Page) -> bool:
    try:
        stealth_module = importlib.import_module("playwright_stealth")
    except ImportError:
        return False

    stealth_sync = getattr(stealth_module, "stealth_sync", None)
    if callable(stealth_sync):
        stealth_sync(page)
        return True
    return False

CHROMIUM_PATH = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
DEFAULT_FILTER = "all"
TARGET_ALIASES: dict[str, str] = {
    "portaljob-madagascar": "portaljob",
}
FILTER_ALIASES: dict[str, str] = {
    "toutes": "all",
    "touteslesoffres": "all",
    "fonctionpublique": "public",
    "free-lance": "freelance",
}


@dataclass(frozen=True)
class PlatformConfig:
    url: str
    filter_selector_type: str
    filters: dict[str, str]


PLATFORMS: dict[str, PlatformConfig] = {
    "asako": PlatformConfig(
        url="https://asako.mg/",
        filter_selector_type="data_tab",
        filters={
            "all": "toutes",
            "cdd": "cdd",
            "cdi": "cdi",
            "stage": "stage",
            "freelance": "freelance",
        },
    ),
    "portaljob": PlatformConfig(
        url="https://www.portaljob-madagascar.com/",
        filter_selector_type="label_text",
        filters={
            "all": "all",
            "cdi": "CDI",
            "cdd": "CDD",
            "public": "Fonction publique",
            "interim": "Intérim",
            "stage": "Stage",
            "freelance": "Free-lance",
        },
    ),
}


def normalize_filter(filter_name: str) -> str:
    normalized_filter = filter_name.strip().lower().replace(" ", "")
    return FILTER_ALIASES.get(normalized_filter, normalized_filter)


def apply_platform_filter(page: Page, config: PlatformConfig, filter_name: str) -> None:
    if filter_name == DEFAULT_FILTER:
        return

    filter_selector_value = config.filters[filter_name]
    if config.filter_selector_type == "data_tab":
        selector = f"ul.filters .item[data-tab='{filter_selector_value}']"
        page.click(selector, timeout=10000)
        page.wait_for_timeout(600)
        return
    if config.filter_selector_type == "label_text":
        page.locator("label", has_text=filter_selector_value).first.click(timeout=10000)
        page.wait_for_timeout(600)
        return

    raise ValueError(f"Unsupported filter selector type '{config.filter_selector_type}'.")


def open_target_homepage(target: str, filter_name: str = DEFAULT_FILTER, timeout_ms: int = 30000) -> dict:
    """
    Opens the requested homepage and returns basic navigation metadata.
    """
    normalized_target = target.strip().lower().replace(" ", "")
    normalized_target = TARGET_ALIASES.get(normalized_target, normalized_target)
    normalized_filter = normalize_filter(filter_name)
    platform_config = PLATFORMS.get(normalized_target)
    if not platform_config:
        allowed_targets = ", ".join(sorted(PLATFORMS.keys()))
        return {
            "success": False,
            "error": f"Unsupported target '{target}'. Allowed values: {allowed_targets}.",
        }
    if normalized_filter not in platform_config.filters:
        allowed_filters = ", ".join(sorted(platform_config.filters.keys()))
        return {
            "success": False,
            "target": normalized_target,
            "filter": normalized_filter,
            "error": f"Unsupported filter '{normalized_filter}' for {normalized_target}. Allowed values: {allowed_filters}.",
        }

    with sync_playwright() as playwright:
        launch_kwargs = {"headless": True}
        if CHROMIUM_PATH:
            launch_kwargs["executable_path"] = CHROMIUM_PATH

        browser = playwright.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        try:
            stealth_applied = apply_stealth(page)
            response = page.goto(platform_config.url, wait_until="domcontentloaded", timeout=timeout_ms)
            apply_platform_filter(page, platform_config, normalized_filter)
            page.wait_for_timeout(1500)
            title = page.title()
            current_url = page.url
            user_agent = page.evaluate("() => navigator.userAgent")

            return {
                "success": True,
                "target": normalized_target,
                "filter": normalized_filter,
                "url": current_url,
                "title": title,
                "user_agent": user_agent,
                "stealth_applied": stealth_applied,
                "status_code": response.status if response else None,
            }
        except PlaywrightTimeoutError:
            return {
                "success": False,
                "error": f"Navigation timeout while opening {platform_config.url}.",
            }
        finally:
            browser.close()
