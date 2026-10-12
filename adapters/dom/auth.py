"""Legacy shims and compatibility exports for authentication and portal scripts."""

from typing import Final

from adapters.dom.lifecycle import (
    CHECK_FORM_LOADING_SCRIPT,
    EXPAND_ALL_SECTIONS_SCRIPT,
)
from adapters.dom.navigation import (
    PORTAL_APPLY_CLICK_SCRIPT,
    PORTAL_DROPDOWN_CLICK_SCRIPT,
)

# Legacy shims (login pages are standard forms handled uniformly by the general engine)
DETECT_LOGIN_PAGE_SCRIPT: Final[str] = """() => {
    const hasUser = document.querySelector('#username, input[type="email"], input[name="username"]');
    const hasPass = document.querySelector('#password, input[type="password"]');
    const title = document.title.toLowerCase();
    return !!(hasPass && (hasUser || title.includes('sign in') || title.includes('login')));
}"""

INJECT_LOGIN_CREDENTIALS_SCRIPT: Final[str] = """([u, p]) => {
    const userEl = document.querySelector('#username, input[type="email"], input[name="username"]');
    const passEl = document.querySelector('#password, input[type="password"]');
    if (userEl) {
        userEl.value = u;
        userEl.dispatchEvent(new Event('input', { bubbles: true }));
        userEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if (passEl) {
        passEl.value = p;
        passEl.dispatchEvent(new Event('input', { bubbles: true }));
        passEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
}"""

__all__ = [
    "DETECT_LOGIN_PAGE_SCRIPT",
    "INJECT_LOGIN_CREDENTIALS_SCRIPT",
    "PORTAL_DROPDOWN_CLICK_SCRIPT",
    "PORTAL_APPLY_CLICK_SCRIPT",
    "CHECK_FORM_LOADING_SCRIPT",
    "EXPAND_ALL_SECTIONS_SCRIPT",
]
