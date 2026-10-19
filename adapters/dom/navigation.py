"""Isolated DOM scripts for job portal landing transitions."""

from typing import Final

PORTAL_DROPDOWN_CLICK_SCRIPT: Final[str] = """() => {
    const toggle = document.querySelector('button.dropdown-toggle, .dropdown-toggle, [data-toggle="dropdown"]');
    if (toggle && toggle.offsetParent !== null) {
        toggle.click();
        return true;
    }
    return false;
}"""

PORTAL_APPLY_CLICK_SCRIPT: Final[str] = """() => {
    // 1. Prioritize inner manual apply option inside opened dropdown
    const manualOpt = document.querySelector('#applyOption-top-manual, .social-apply-option a, a.applyOption');
    if (manualOpt && manualOpt.offsetParent !== null) {
        manualOpt.click();
        return true;
    }

    // 2. Search for explicit apply buttons/links that are not dropdown toggles
    const links = Array.from(document.querySelectorAll('a, button, input[type="button"]'));
    const applyBtn = links.find(el => {
        if (el.classList.contains('dropdown-toggle')) return false;
        const t = (el.innerText || el.value || '').trim().toLowerCase();
        return t === 'apply now' || t === 'apply' || t === 'easy apply' || t === 'quick apply' || t === 'apply now »' || el.classList.contains('dialogApplyBtn') || el.classList.contains('jobs-apply-button') || el.classList.contains('overview-apply-btn');
    });
    if (applyBtn && applyBtn.offsetParent !== null) {
        applyBtn.click();
        return true;
    }
    return false;
}"""
