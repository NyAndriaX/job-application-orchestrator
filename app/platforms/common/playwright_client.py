from __future__ import annotations

import importlib
import shutil
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Browser
from playwright.sync_api import Page
from playwright.sync_api import Playwright
from playwright.sync_api import sync_playwright

CHROMIUM_PATH = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")


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


def launch_browser(playwright: Playwright) -> Browser:
    launch_kwargs = {"headless": False}
    if CHROMIUM_PATH:
        launch_kwargs["executable_path"] = CHROMIUM_PATH
    return playwright.chromium.launch(**launch_kwargs)


@contextmanager
def playwright_page() -> Iterator[tuple[Page, bool]]:
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        try:
            stealth_applied = apply_stealth(page)
            yield page, stealth_applied
        finally:
            browser.close()
