from __future__ import annotations

import logging
import random
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.platforms.common.playwright_client import playwright_page

logger = logging.getLogger(__name__)

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


def human_pause(page, min_ms: int = 500, max_ms: int = 1400) -> None:
    page.wait_for_timeout(random.randint(min_ms, max_ms))


def normalize_filter(filter_name: str) -> str:
    normalized_filter = filter_name.strip().lower().replace(" ", "")
    return FILTER_ALIASES.get(normalized_filter, normalized_filter)


def navigate_with_fallback(page, url: str, timeout_ms: int):
    try:
        human_pause(page, 700, 1800)
        logger.info("[asako] Navigating to %s (domcontentloaded)", url)
        return page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        logger.warning("[asako] domcontentloaded timeout on %s, retry with commit", url)
        return page.goto(url, wait_until="commit", timeout=timeout_ms)


def ensure_authenticated_or_open_login(page) -> dict[str, bool]:
    logger.info("[asako] Checking authentication state from header")
    account_menu = page.locator("button[aria-label='Menu utilisateur']")
    if account_menu.count() > 0:
        logger.info("[asako] Session already authenticated")
        return {"is_authenticated": True, "login_clicked": False}

    login_link = page.locator("a[href='/connexion']").first
    if login_link.count() > 0:
        try:
            logger.info("[asako] Clicking 'Connexion' link")
            human_pause(page, 600, 1600)
            login_link.click(timeout=10000)
            page.wait_for_url("**/connexion", timeout=8000)
            logger.info("[asako] Reached login page via header link")
        except PlaywrightTimeoutError:
            logger.warning("[asako] Login link flow timeout, forcing /connexion")
            navigate_with_fallback(page, "https://asako.mg/connexion", timeout_ms=20000)
        return {"is_authenticated": False, "login_clicked": True}

    logger.warning("[asako] Login link not found, forcing /connexion")
    navigate_with_fallback(page, "https://asako.mg/connexion", timeout_ms=20000)
    return {"is_authenticated": False, "login_clicked": False}


def wait_for_stable_page(page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=7000)
    except PlaywrightTimeoutError:
        logger.warning("[asako] domcontentloaded wait timeout during stabilization")
    try:
        page.wait_for_load_state("load", timeout=7000)
    except PlaywrightTimeoutError:
        logger.warning("[asako] load wait timeout during stabilization")
    human_pause(page, 700, 1400)


def safe_auth_state_check(page, timeout_ms: int) -> dict[str, bool]:
    attempts = 2
    for attempt in range(1, attempts + 1):
        wait_for_stable_page(page)
        try:
            return ensure_authenticated_or_open_login(page)
        except Exception as exc:
            message = str(exc)
            if "Execution context was destroyed" in message and attempt < attempts:
                logger.warning("[asako] Auth check raced navigation, retrying (%s/%s)", attempt, attempts)
                navigate_with_fallback(page, page.url, timeout_ms=timeout_ms)
                continue
            raise
    return {"is_authenticated": False, "login_clicked": False}


def restore_session_storage(page, session_storage: dict[str, str]) -> None:
    logger.info("[asako] Restoring sessionStorage with %s keys", len(session_storage))
    page.evaluate(
        """
        (payload) => {
          Object.entries(payload).forEach(([key, value]) => {
            sessionStorage.setItem(key, value);
          });
        }
        """,
        session_storage,
    )


def restore_browser_state(page, browser_state: dict[str, Any]) -> None:
    cookies = browser_state.get("cookies") or []
    local_storage = browser_state.get("local_storage") or {}
    session_storage = browser_state.get("session_storage") or {}

    if isinstance(cookies, list) and cookies:
        logger.info("[asako] Restoring cookies with %s entries", len(cookies))
        page.context.add_cookies(cookies)

    if isinstance(local_storage, dict) and local_storage:
        logger.info("[asako] Restoring localStorage with %s keys", len(local_storage))
        page.evaluate(
            """
            (payload) => {
              Object.entries(payload).forEach(([key, value]) => {
                localStorage.setItem(key, value);
              });
            }
            """,
            local_storage,
        )

    if isinstance(session_storage, dict) and session_storage:
        restore_session_storage(page, session_storage)


def export_session_storage(page) -> dict[str, str]:
    payload = page.evaluate(
        """() => Object.fromEntries(
            Array.from({ length: sessionStorage.length }, (_, i) => {
              const key = sessionStorage.key(i);
              return [key, sessionStorage.getItem(key)];
            })
          )"""
    )
    logger.info("[asako] Exported sessionStorage with %s keys", len(payload))
    return payload


def export_local_storage(page) -> dict[str, str]:
    payload = page.evaluate(
        """() => Object.fromEntries(
            Array.from({ length: localStorage.length }, (_, i) => {
              const key = localStorage.key(i);
              return [key, localStorage.getItem(key)];
            })
          )"""
    )
    logger.info("[asako] Exported localStorage with %s keys", len(payload))
    return payload


def export_browser_state(page) -> dict[str, Any]:
    cookies = page.context.cookies()
    local_storage = export_local_storage(page)
    session_storage = export_session_storage(page)
    logger.info("[asako] Exported browser_state cookies=%s", len(cookies))
    return {
        "cookies": cookies,
        "local_storage": local_storage,
        "session_storage": session_storage,
    }


def submit_login_form(page, email: str, password: str) -> dict[str, Any]:
    logger.info("[asako] Submitting login form for %s", email)
    email_input = page.locator("#login-email")
    password_input = page.locator("#login-password")
    if email_input.count() == 0 or password_input.count() == 0:
        logger.error("[asako] Login form fields not found on /connexion")
        return {"submitted": False, "error": "Login form not found on /connexion."}

    human_pause(page, 700, 1700)
    email_input.click(timeout=10000)
    human_pause(page, 200, 700)
    email_input.fill("")
    page.keyboard.type(email, delay=random.randint(45, 110))

    human_pause(page, 500, 1300)
    password_input.click(timeout=10000)
    human_pause(page, 200, 700)
    password_input.fill("")
    page.keyboard.type(password, delay=random.randint(45, 110))

    human_pause(page, 800, 2000)
    page.locator("button[type='submit']").first.click(timeout=10000)

    try:
        page.wait_for_url(lambda value: "/connexion" not in value, timeout=15000)
    except PlaywrightTimeoutError:
        logger.warning("[asako] Login submit did not redirect out of /connexion in time")

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeoutError:
        logger.warning("[asako] networkidle wait timeout after login submit")
    human_pause(page, 800, 1800)

    on_dashboard = "/candidat/dashboard" in page.url
    login_form_visible = page.locator("#login-email").count() > 0 and page.locator("#login-password").count() > 0
    auth_error_visible = page.locator("text=Email ou mot de passe incorrect.").count() > 0
    has_account_menu = page.locator("button[aria-label='Menu utilisateur']").count() > 0
    is_authenticated = has_account_menu or on_dashboard or (not login_form_visible and not auth_error_visible)
    logger.info(
        "[asako] Login submitted, authenticated=%s dashboard=%s account_menu=%s login_form_visible=%s auth_error_visible=%s current_url=%s",
        is_authenticated,
        on_dashboard,
        has_account_menu,
        login_form_visible,
        auth_error_visible,
        page.url,
    )
    return {
        "submitted": True,
        "is_authenticated": is_authenticated,
        "auth_error_visible": auth_error_visible,
        "current_url": page.url,
    }


def run_platform_session(auth: dict[str, Any], filter_name: str = DEFAULT_FILTER, timeout_ms: int = 30000) -> dict:
    logger.info("[asako] Starting platform session with filter=%s", filter_name)
    normalized_filter = normalize_filter(filter_name)
    if normalized_filter not in FILTER_VALUES:
        allowed_filters = ", ".join(sorted(FILTER_VALUES.keys()))
        return {
            "success": False,
            "target": "asako",
            "filter": normalized_filter,
            "error": f"Unsupported filter '{normalized_filter}' for asako. Allowed values: {allowed_filters}.",
        }

    with playwright_page() as (page, stealth_applied):
        try:
            response = navigate_with_fallback(page, "https://asako.mg/", timeout_ms=timeout_ms)
            logger.info("[asako] Homepage loaded, status=%s", response.status if response else None)
            restored_session = False
            restored_browser_state = False
            browser_state = auth.get("browser_state")
            if isinstance(browser_state, dict) and browser_state:
                restore_browser_state(page, browser_state)
                restored_browser_state = True
                page.reload(wait_until="commit", timeout=timeout_ms)
                logger.info("[asako] Page reloaded after browser_state restore")

            session_storage = auth.get("session_storage")
            if not restored_browser_state and isinstance(session_storage, dict) and session_storage:
                restore_session_storage(page, session_storage)
                restored_session = True
                page.reload(wait_until="commit", timeout=timeout_ms)
                logger.info("[asako] Page reloaded after session restore")

            auth_state = safe_auth_state_check(page, timeout_ms=timeout_ms)
            login_submitted = False

            if not auth_state["is_authenticated"] and page.url.endswith("/connexion"):
                logger.info("[asako] Login required on /connexion")
                email = auth.get("email")
                password = auth.get("password")
                if isinstance(email, str) and isinstance(password, str) and email and password:
                    max_login_attempts = 2
                    for attempt in range(1, max_login_attempts + 1):
                        logger.info("[asako] Login attempt %s/%s", attempt, max_login_attempts)
                        login_result = submit_login_form(page, email, password)
                        if not login_result.get("submitted"):
                            return {
                                "success": False,
                                "target": "asako",
                                "filter": normalized_filter,
                                "error": login_result.get("error", "Could not submit login form."),
                            }
                        login_submitted = True
                        auth_state["is_authenticated"] = bool(login_result.get("is_authenticated"))
                        if auth_state["is_authenticated"]:
                            break
                        if login_result.get("auth_error_visible"):
                            return {
                                "success": False,
                                "target": "asako",
                                "filter": normalized_filter,
                                "error": "Email ou mot de passe incorrect.",
                            }
                        if attempt < max_login_attempts:
                            logger.warning("[asako] No redirect and no auth error; retrying login after refresh")
                            navigate_with_fallback(page, "https://asako.mg/connexion", timeout_ms=timeout_ms)
                    if not auth_state["is_authenticated"]:
                        return {
                            "success": False,
                            "target": "asako",
                            "filter": normalized_filter,
                            "error": "Authentication did not complete after retry on /connexion.",
                        }
                else:
                    logger.error("[asako] Missing credentials and reusable session")
                    return {
                        "success": False,
                        "target": "asako",
                        "filter": normalized_filter,
                        "error": "Asako requires email/password or reusable session_storage when login is needed.",
                    }

            if normalized_filter != DEFAULT_FILTER:
                filter_selector_value = FILTER_VALUES[normalized_filter]
                selector = f"ul.filters .item[data-tab='{filter_selector_value}']"
                logger.info("[asako] Applying filter '%s' using selector %s", normalized_filter, selector)
                try:
                    human_pause(page, 600, 1800)
                    page.click(selector, timeout=10000)
                    page.wait_for_timeout(600)
                    filter_applied = True
                    filter_warning = None
                except PlaywrightTimeoutError:
                    filter_applied = False
                    filter_warning = (
                        f"Filter selector not found on current page for '{normalized_filter}'. "
                        "Authentication succeeded but filter could not be applied."
                    )
                    logger.warning("[asako] %s", filter_warning)
            else:
                filter_applied = True
                filter_warning = None

            page.wait_for_timeout(1500)
            exported_browser_state = export_browser_state(page)
            exported_session_storage = exported_browser_state.get("session_storage") or {}
            logger.info(
                "[asako] Session flow complete authenticated=%s login_clicked=%s login_submitted=%s",
                auth_state["is_authenticated"],
                auth_state["login_clicked"],
                login_submitted,
            )
            return {
                "success": True,
                "target": "asako",
                "filter": normalized_filter,
                "url": page.url,
                "title": page.title(),
                "user_agent": page.evaluate("() => navigator.userAgent"),
                "stealth_applied": stealth_applied,
                "status_code": response.status if response else None,
                "is_authenticated": auth_state["is_authenticated"],
                "login_clicked": auth_state["login_clicked"],
                "login_submitted": login_submitted,
                "session_restored": restored_session,
                "browser_state_restored": restored_browser_state,
                "browser_state": exported_browser_state,
                "session_storage": exported_session_storage,
                "filter_applied": filter_applied,
                "filter_warning": filter_warning,
            }
        except PlaywrightTimeoutError:
            logger.exception("[asako] Playwright timeout during automation")
            return {
                "success": False,
                "error": "Navigation timeout while opening https://asako.mg/.",
            }
        except Exception as exc:
            logger.exception("[asako] Unexpected automation failure")
            return {
                "success": False,
                "error": f"Asako automation failed: {exc}",
            }
