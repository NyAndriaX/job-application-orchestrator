from __future__ import annotations

import logging
import random
import unicodedata
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.platforms.common.playwright_client import playwright_page

logger = logging.getLogger(__name__)

DEFAULT_FILTER = "all"
ASAKO_JOBS_URL = "https://www.asako.mg/emploi"
ASAKO_LOGIN_URL = "https://www.asako.mg/connexion"
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
CONTRACT_TYPES = {"cdi", "cdd", "stage", "freelance"}


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


def extract_visible_offers(page) -> list[dict[str, Any]]:
    offers = page.evaluate(
        """() => {
            const contractTypes = new Set(["CDI", "CDD", "STAGE", "FREELANCE"]);
            const cards = Array.from(document.querySelectorAll("a[href^='/annonces/']"));
            const seen = new Set();
            const rows = [];
            const normalizeToken = (value) => (value || "").replace(/\\s+/g, " ").replace(/^↻\\s*/, "").trim();
            const isDateLabel = (value) => /^(il y a\\b|hier\\b|aujourd|today\\b|yesterday\\b)/i.test(value);

            for (const card of cards) {
              const href = card.getAttribute("href") || "";
              if (!href || seen.has(href)) continue;
              seen.add(href);

              const clean = (v) => (v || "").replace(/\\s+/g, " ").trim();
              const title = clean(card.querySelector(".text-navy-title")?.textContent);
              const company = clean(
                card.querySelector("div.text-sm.font-medium, div[style*='A78BCD']")?.textContent
              );
              if (!title) continue;

              const rawSpanTexts = Array.from(card.querySelectorAll("span"))
                .map((el) => normalizeToken(el.textContent))
                .filter(Boolean);
              const postedLabel =
                rawSpanTexts.find((text) => isDateLabel(text)) || "";

              let contract = "";
              const chipsUpper = rawSpanTexts.map((text) => text.toUpperCase());
              for (const text of chipsUpper) {
                if (contractTypes.has(text)) {
                  contract = text;
                  break;
                }
              }

              const nonMeta = rawSpanTexts.filter((text) => {
                const upper = text.toUpperCase();
                return text !== "·" && !isDateLabel(text) && !contractTypes.has(upper) && text.toLowerCase() !== "sponsorisé";
              });
              const location = nonMeta[0] || "";
              const sector = nonMeta[1] || "";

              rows.push({
                href,
                url: new URL(href, window.location.origin).toString(),
                title,
                company,
                location,
                sector,
                contract: contract.toLowerCase(),
                sponsored: rawSpanTexts.some((text) => text.toLowerCase() === "sponsorisé"),
                posted_label: postedLabel,
              });
            }
            return rows;
        }"""
    )
    return offers if isinstance(offers, list) else []


def collect_all_offers(page, max_clicks: int = 12) -> list[dict[str, Any]]:
    for _ in range(max_clicks):
        current_offers = extract_visible_offers(page)
        # Asako list is sorted newest -> oldest; once "hier" appears, no need to go deeper.
        if any(is_offer_older_than_today(offer) for offer in current_offers):
            break
        before_count = len(current_offers)
        load_more_button = page.locator("button:has-text(\"Charger plus\")").first
        if load_more_button.count() == 0:
            break
        try:
            human_pause(page, 400, 900)
            load_more_button.click(timeout=5000)
            page.wait_for_timeout(1200)
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except PlaywrightTimeoutError:
                pass
        except PlaywrightTimeoutError:
            logger.warning("[asako] Could not click 'Charger plus', keeping current offers list")
            break
        updated_offers = extract_visible_offers(page)
        after_count = len(updated_offers)
        if after_count <= before_count:
            break
        if any(is_offer_older_than_today(offer) for offer in updated_offers):
            break
    return extract_visible_offers(page)


def filter_offers_by_contract(offers: list[dict[str, Any]], normalized_filters: list[str]) -> list[dict[str, Any]]:
    if not normalized_filters or DEFAULT_FILTER in normalized_filters:
        return offers
    allowed_contracts = [value for value in normalized_filters if value in CONTRACT_TYPES]
    if not allowed_contracts:
        return offers
    allowed_set = set(allowed_contracts)
    return [offer for offer in offers if str(offer.get("contract", "")).strip().lower() in allowed_set]


def is_offer_from_today(offer: dict[str, Any]) -> bool:
    posted_label = str(offer.get("posted_label", "")).strip().lower()
    if not posted_label:
        return False
    if posted_label.startswith("hier") or "yesterday" in posted_label:
        return False
    return (
        posted_label.startswith("il y a")
        or posted_label.startswith("aujourd")
        or posted_label.startswith("today")
    )


def is_offer_older_than_today(offer: dict[str, Any]) -> bool:
    posted_label = str(offer.get("posted_label", "")).strip().lower()
    return posted_label.startswith("hier") or "yesterday" in posted_label


def normalize_keywords(values: list[str]) -> list[str]:
    return [item.strip().lower() for item in values if isinstance(item, str) and item.strip()]


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_only.lower()


def keyword_matches_text(keyword: str, text: str) -> bool:
    normalized_keyword = normalize_text(keyword).strip()
    normalized_text = normalize_text(text)
    if not normalized_keyword:
        return False
    if normalized_keyword in normalized_text:
        return True
    # Fuzzy root match for close forms like "automation" <-> "automatisation".
    root = normalized_keyword[:6]
    if len(root) < 4:
        return False
    return any(token.startswith(root) for token in normalized_text.split())


def score_offers_by_skills(
    offers: list[dict[str, Any]],
    skills: list[str],
    excluded_keywords: list[str],
    min_relevance_score: int = 1,
) -> list[dict[str, Any]]:
    normalized_skills = normalize_keywords(skills)
    normalized_excluded = normalize_keywords(excluded_keywords)

    if not normalized_skills and not normalized_excluded:
        return [{**offer, "relevance_score": 0, "matched_skills": []} for offer in offers]

    scored: list[dict[str, Any]] = []
    for offer in offers:
        title_text = str(offer.get("title", ""))
        sector_text = str(offer.get("sector", ""))
        company_text = str(offer.get("company", ""))
        location_text = str(offer.get("location", ""))
        contract_text = str(offer.get("contract", ""))
        searchable_text = " ".join([title_text, sector_text, company_text, location_text, contract_text])

        if normalized_excluded and any(keyword_matches_text(keyword, searchable_text) for keyword in normalized_excluded):
            continue

        relevance_score = 0
        matched_skills: list[str] = []
        for keyword in normalized_skills:
            matched = False
            if keyword_matches_text(keyword, title_text):
                relevance_score += 3
                matched = True
            if keyword_matches_text(keyword, sector_text):
                relevance_score += 2
                matched = True
            if keyword_matches_text(keyword, company_text):
                relevance_score += 1
                matched = True
            if keyword_matches_text(keyword, location_text) or keyword_matches_text(keyword, contract_text):
                relevance_score += 1
                matched = True
            if matched:
                matched_skills.append(keyword)

        if normalized_skills and relevance_score < max(min_relevance_score, 0):
            continue

        scored.append(
            {
                **offer,
                "relevance_score": relevance_score,
                "matched_skills": sorted(set(matched_skills)),
            }
        )

    scored.sort(key=lambda offer: (int(offer.get("relevance_score", 0)), str(offer.get("posted_label", ""))), reverse=True)
    return scored


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
            navigate_with_fallback(page, ASAKO_LOGIN_URL, timeout_ms=20000)
        return {"is_authenticated": False, "login_clicked": True}

    logger.warning("[asako] Login link not found, forcing /connexion")
    navigate_with_fallback(page, ASAKO_LOGIN_URL, timeout_ms=20000)
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


def apply_to_single_offer(page, offer: dict[str, Any], timeout_ms: int) -> dict[str, Any]:
    job_url = str(offer.get("url", "")).strip()
    if not job_url:
        return {"status": "failed", "message": "Missing offer URL."}

    navigate_with_fallback(page, job_url, timeout_ms=timeout_ms)
    wait_for_stable_page(page)

    page_text_before = page.inner_text("body")[:5000].lower()
    already_applied_markers = (
        "candidature envoyee",
        "candidature envoyée",
        "vous avez deja postule",
        "vous avez déjà postulé",
        "deja postule a cette offre",
        "déjà postulé à cette offre",
    )
    if any(marker in page_text_before for marker in already_applied_markers):
        return {"status": "applied", "message": "Already applied state detected on offer page."}

    apply_button = page.locator(
        "button:has-text('Postuler maintenant'), button:has-text('Postuler'), a:has-text('Postuler')"
    ).first
    if apply_button.count() == 0:
        return {"status": "skipped", "message": "Apply button not found on job page."}

    try:
        human_pause(page, 400, 900)
        apply_button.click(timeout=8000)
        page.wait_for_timeout(1200)
    except PlaywrightTimeoutError:
        return {"status": "failed", "message": "Timed out while clicking apply button."}

    page_text = page.inner_text("body")[:5000].lower()
    if any(marker in page_text for marker in already_applied_markers):
        return {"status": "applied", "message": "Application already marked as sent on page."}
    # If modal opened, treat as applied attempt.
    if "email" in page_text and "mot de passe" in page_text and "postuler" in page_text:
        return {"status": "applied", "message": "Apply modal opened and submission flow started."}
    return {"status": "applied", "message": "Apply button clicked."}


def run_apply_session(auth: dict[str, Any], offers: list[dict[str, Any]], timeout_ms: int = 30000) -> list[dict[str, Any]]:
    if not offers:
        return []

    results: list[dict[str, Any]] = []
    with playwright_page() as (page, _):
        navigate_with_fallback(page, ASAKO_JOBS_URL, timeout_ms=timeout_ms)
        browser_state = auth.get("browser_state")
        if isinstance(browser_state, dict) and browser_state:
            restore_browser_state(page, browser_state)
            page.reload(wait_until="commit", timeout=timeout_ms)
        wait_for_stable_page(page)

        for offer in offers:
            try:
                apply_result = apply_to_single_offer(page, offer, timeout_ms=timeout_ms)
            except Exception as exc:
                apply_result = {"status": "failed", "message": f"Unexpected error while applying: {exc}"}
            results.append({"job_url": offer.get("url"), **apply_result})
    return results


def run_platform_session(
    auth: dict[str, Any],
    filter_name: str = DEFAULT_FILTER,
    filter_names: list[str] | None = None,
    timeout_ms: int = 30000,
    skills: list[str] | None = None,
    excluded_keywords: list[str] | None = None,
    min_relevance_score: int = 1,
    max_jobs: int = 20,
) -> dict:
    try:
        normalized_min_relevance_score = max(int(min_relevance_score), 0)
    except (TypeError, ValueError):
        normalized_min_relevance_score = 1
    try:
        normalized_max_jobs = max(int(max_jobs), 1)
    except (TypeError, ValueError):
        normalized_max_jobs = 20

    requested_filters = filter_names or [filter_name]
    normalized_filters = [normalize_filter(str(value)) for value in requested_filters if str(value).strip()]
    if not normalized_filters:
        normalized_filters = [DEFAULT_FILTER]

    logger.info("[asako] Starting platform session with filters=%s", normalized_filters)
    invalid_filters = [value for value in normalized_filters if value not in FILTER_VALUES]
    if invalid_filters:
        allowed_filters = ", ".join(sorted(FILTER_VALUES.keys()))
        return {
            "success": False,
            "target": "asako",
            "filters": normalized_filters,
            "error": f"Unsupported filter(s) {invalid_filters} for asako. Allowed values: {allowed_filters}.",
        }

    with playwright_page() as (page, stealth_applied):
        try:
            response = navigate_with_fallback(page, ASAKO_JOBS_URL, timeout_ms=timeout_ms)
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
                                "filters": normalized_filters,
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
                                "filters": normalized_filters,
                                "error": "Email ou mot de passe incorrect.",
                            }
                        if attempt < max_login_attempts:
                            logger.warning("[asako] No redirect and no auth error; retrying login after refresh")
                            navigate_with_fallback(page, ASAKO_LOGIN_URL, timeout_ms=timeout_ms)
                    if not auth_state["is_authenticated"]:
                        return {
                            "success": False,
                            "target": "asako",
                            "filters": normalized_filters,
                            "error": "Authentication did not complete after retry on /connexion.",
                        }
                else:
                    logger.error("[asako] Missing credentials and reusable session")
                    return {
                        "success": False,
                        "target": "asako",
                        "filters": normalized_filters,
                        "error": "Asako requires email/password or reusable session_storage when login is needed.",
                    }

            if DEFAULT_FILTER not in normalized_filters:
                logger.info("[asako] UI filter disabled, collecting all offers then filtering %s in code", normalized_filters)
            filter_applied = True
            filter_warning = None

            all_offers = collect_all_offers(page)
            today_offers = [offer for offer in all_offers if is_offer_from_today(offer)]
            matched_offers = filter_offers_by_contract(today_offers, normalized_filters)
            ranked_offers = score_offers_by_skills(
                matched_offers,
                skills=skills or [],
                excluded_keywords=excluded_keywords or [],
                min_relevance_score=normalized_min_relevance_score,
            )
            ranked_offers = ranked_offers[:normalized_max_jobs]
            logger.info(
                "[asako] Offers collected=%s today=%s matched=%s for filter=%s",
                len(all_offers),
                len(today_offers),
                len(ranked_offers),
                normalized_filters,
            )

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
                "filter": normalized_filters[0],
                "filters": normalized_filters,
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
                "offers_collected_count": len(all_offers),
                "offers_today_count": len(today_offers),
                "offers_matched_count": len(ranked_offers),
                "all_offers": all_offers,
                "today_offers": today_offers,
                "filtered_offers": ranked_offers,
                "skills_applied": normalize_keywords(skills or []),
                "excluded_keywords_applied": normalize_keywords(excluded_keywords or []),
                "min_relevance_score_applied": normalized_min_relevance_score,
                "max_jobs_applied": normalized_max_jobs,
            }
        except PlaywrightTimeoutError:
            logger.exception("[asako] Playwright timeout during automation")
            return {
                "success": False,
                "error": f"Navigation timeout while opening {ASAKO_JOBS_URL}.",
            }
        except Exception as exc:
            logger.exception("[asako] Unexpected automation failure")
            return {
                "success": False,
                "error": f"Asako automation failed: {exc}",
            }
