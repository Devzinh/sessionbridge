from typing import Any, Dict
from playwright.async_api import Page


CLOUDFLARE_TITLE_PATTERNS = [
    "just a moment...",
    "attention required! | cloudflare",
    "ddos-guard",
    "security check",
    "please wait...",
]

CLOUDFLARE_DOM_SELECTORS = [
    "iframe[src*='challenges.cloudflare.com']",
    "div#cf-turnstile",
    "div.cf-turnstile",
    "#challenge-stage",
    "#cf-challenge-running",
    "form#challenge-form",
    ".ray-id",
]

CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    ".g-recaptcha",
    ".h-captcha",
    "#captcha-box",
]


async def inspect_page_state(page: Page) -> Dict[str, Any]:
    """
    Analyzes the current page to determine if manual human interaction (e.g. Cloudflare,
    Turnstile, CAPTCHA, or verification check) is currently blocking progress.
    """
    try:
        url = page.url
        title = await page.title()
    except Exception as e:
        return {
            "connected": False,
            "url": "",
            "title": "",
            "manual_interaction_required": False,
            "reason": f"Page error or disconnected: {str(e)}",
            "ready": False,
        }

    lower_title = title.lower()

    # 1. Check title indicators
    for pat in CLOUDFLARE_TITLE_PATTERNS:
        if pat in lower_title:
            return {
                "connected": True,
                "url": url,
                "title": title,
                "manual_interaction_required": True,
                "reason": f"Cloudflare / anti-bot challenge detected in page title ('{title}')",
                "ready": False,
            }

    # 2. Check DOM selectors for Cloudflare / Turnstile challenges
    for sel in CLOUDFLARE_DOM_SELECTORS:
        try:
            elem = await page.query_selector(sel)
            if elem and await elem.is_visible():
                return {
                    "connected": True,
                    "url": url,
                    "title": title,
                    "manual_interaction_required": True,
                    "reason": f"Cloudflare challenge element detected ({sel})",
                    "ready": False,
                }
        except Exception as e:
            return {
                "connected": False,
                "url": url,
                "title": title,
                "manual_interaction_required": False,
                "reason": f"Page inspection error while checking selector ({sel}): {str(e)}",
                "ready": False,
            }

    # 3. Check for general Captchas
    for sel in CAPTCHA_SELECTORS:
        try:
            elem = await page.query_selector(sel)
            if elem and await elem.is_visible():
                return {
                    "connected": True,
                    "url": url,
                    "title": title,
                    "manual_interaction_required": True,
                    "reason": f"CAPTCHA element detected ({sel})",
                    "ready": False,
                }
        except Exception as e:
            return {
                "connected": False,
                "url": url,
                "title": title,
                "manual_interaction_required": False,
                "reason": f"Page inspection error while checking selector ({sel}): {str(e)}",
                "ready": False,
            }

    # 4. Check page text indicators
    try:
        body_text = await page.evaluate("() => (document.body ? document.body.innerText.slice(0, 2000) : '')")
        lower_body = body_text.lower()
        if "verify you are human" in lower_body or "verifying you are human" in lower_body:
            return {
                "connected": True,
                "url": url,
                "title": title,
                "manual_interaction_required": True,
                "reason": "Challenge prompt detected: 'Verify you are human'",
                "ready": False,
            }
        if "enable javascript and cookies to continue" in lower_body:
            return {
                "connected": True,
                "url": url,
                "title": title,
                "manual_interaction_required": True,
                "reason": "Bot verification / cookie clearance required",
                "ready": False,
            }
    except Exception as e:
        return {
            "connected": False,
            "url": url,
            "title": title,
            "manual_interaction_required": False,
            "reason": f"Page inspection error while reading body text: {str(e)}",
            "ready": False,
        }

    # If nothing blocked, page is ready
    return {
        "connected": True,
        "url": url,
        "title": title,
        "manual_interaction_required": False,
        "reason": "Normal page state",
        "ready": True,
    }
