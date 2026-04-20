import importlib
import shutil

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
TARGET_URLS: dict[str, str] = {
    "asako": "https://asako.mg/",
    "portaljob": "https://www.portaljob-madagascar.com/",
}
TARGET_ALIASES: dict[str, str] = {
    "portaljob-madagascar": "portaljob",
}


def open_target_homepage(target: str, timeout_ms: int = 30000) -> dict:
    """
    Opens the requested homepage and returns basic navigation metadata.
    """
    normalized_target = target.strip().lower().replace(" ", "")
    normalized_target = TARGET_ALIASES.get(normalized_target, normalized_target)
    target_url = TARGET_URLS.get(normalized_target)
    if not target_url:
        allowed_targets = ", ".join(sorted(TARGET_URLS.keys()))
        return {
            "success": False,
            "error": f"Unsupported target '{target}'. Allowed values: {allowed_targets}.",
        }

    with sync_playwright() as playwright:
        launch_kwargs = {"headless": True}
        if CHROMIUM_PATH:
            launch_kwargs["executable_path"] = CHROMIUM_PATH

        browser = playwright.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        try:
            stealth_applied = apply_stealth(page)
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)
            title = page.title()
            current_url = page.url
            user_agent = page.evaluate("() => navigator.userAgent")

            return {
                "success": True,
                "target": normalized_target,
                "url": current_url,
                "title": title,
                "user_agent": user_agent,
                "stealth_applied": stealth_applied,
                "status_code": response.status if response else None,
            }
        except PlaywrightTimeoutError:
            return {
                "success": False,
                "error": f"Navigation timeout while opening {target_url}.",
            }
        finally:
            browser.close()
