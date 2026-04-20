from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def open_asako_homepage(timeout_ms: int = 30000) -> dict:
    """
    Opens asako.mg homepage and returns basic navigation metadata.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            response = page.goto("https://asako.mg/", wait_until="domcontentloaded", timeout=timeout_ms)
            title = page.title()
            current_url = page.url

            return {
                "success": True,
                "url": current_url,
                "title": title,
                "status_code": response.status if response else None,
            }
        except PlaywrightTimeoutError:
            return {
                "success": False,
                "error": "Navigation timeout while opening asako.mg.",
            }
        finally:
            browser.close()
