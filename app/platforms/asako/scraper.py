from __future__ import annotations

from typing import Any

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


def ensure_authenticated_or_open_login(page) -> dict[str, bool]:
    account_menu = page.locator("button[aria-label='Menu utilisateur']")
    if account_menu.count() > 0:
        return {"is_authenticated": True, "login_clicked": False}

    login_link = page.locator("a[href='/connexion']").first
    if login_link.count() > 0:
        login_link.click(timeout=10000)
        page.wait_for_url("**/connexion", timeout=15000)
        return {"is_authenticated": False, "login_clicked": True}

    return {"is_authenticated": False, "login_clicked": False}


def restore_session_storage(page, session_storage: dict[str, str]) -> None:
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


def export_session_storage(page) -> dict[str, str]:
    return page.evaluate(
        """() => Object.fromEntries(
            Array.from({ length: sessionStorage.length }, (_, i) => {
              const key = sessionStorage.key(i);
              return [key, sessionStorage.getItem(key)];
            })
          )"""
    )


def submit_login_form(page, email: str, password: str) -> dict[str, Any]:
    email_input = page.locator("#login-email")
    password_input = page.locator("#login-password")
    if email_input.count() == 0 or password_input.count() == 0:
        return {"submitted": False, "error": "Login form not found on /connexion."}

    email_input.fill(email)
    password_input.fill(password)
    page.locator("button[type='submit']").first.click(timeout=10000)

    try:
        page.wait_for_url(lambda value: "/connexion" not in value, timeout=15000)
    except PlaywrightTimeoutError:
        pass

    is_authenticated = page.locator("button[aria-label='Menu utilisateur']").count() > 0
    return {"submitted": True, "is_authenticated": is_authenticated}


def run_platform_session(auth: dict[str, Any], filter_name: str = DEFAULT_FILTER, timeout_ms: int = 30000) -> dict:
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
            response = page.goto("https://asako.mg/", wait_until="domcontentloaded", timeout=timeout_ms)
            restored_session = False
            session_storage = auth.get("session_storage")
            if isinstance(session_storage, dict) and session_storage:
                restore_session_storage(page, session_storage)
                restored_session = True
                page.reload(wait_until="domcontentloaded", timeout=timeout_ms)

            auth_state = ensure_authenticated_or_open_login(page)
            login_submitted = False

            if not auth_state["is_authenticated"] and page.url.endswith("/connexion"):
                email = auth.get("email")
                password = auth.get("password")
                if isinstance(email, str) and isinstance(password, str) and email and password:
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
                else:
                    return {
                        "success": False,
                        "target": "asako",
                        "filter": normalized_filter,
                        "error": "Asako requires email/password or reusable session_storage when login is needed.",
                    }

            if normalized_filter != DEFAULT_FILTER:
                filter_selector_value = FILTER_VALUES[normalized_filter]
                selector = f"ul.filters .item[data-tab='{filter_selector_value}']"
                page.click(selector, timeout=10000)
                page.wait_for_timeout(600)

            page.wait_for_timeout(1500)
            exported_session_storage = export_session_storage(page)
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
                "session_storage": exported_session_storage,
            }
        except PlaywrightTimeoutError:
            return {
                "success": False,
                "error": "Navigation timeout while opening https://asako.mg/.",
            }
