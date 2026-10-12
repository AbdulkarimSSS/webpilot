"""Isolated DOM script for reactive button clicking and dialog dismissing."""

from typing import Final

CLICK_BUTTON_DOM_SCRIPT: Final[str] = """(t) => {
    let rawTarget = (t || '').trim();
    let scopeText = null;
    if (rawTarget.includes('>>')) {
        const parts = rawTarget.split('>>').map(s => s.trim()).filter(Boolean);
        if (parts.length >= 2) {
            scopeText = parts[0].toLowerCase();
            rawTarget = parts[parts.length - 1];
        }
    }
    const cleanText = (s) => (s || '').replace(/[\\uE000-\\uF8FF]/g, ' ').replace(/\\s+/g, ' ').trim().toLowerCase();
    const lower = cleanText(rawTarget);

    let searchRoot = document;
    if (scopeText) {
        const sections = Array.from(document.querySelectorAll('fieldset, section, .rcmFormSection, .form-section, .panel, .card, [id$=":sectionContent"], div'));
        const matchedSec = sections.find(sec => {
            const h = sec.querySelector('legend, h1, h2, h3, h4, .sectionHeader, .panel-title, [id$=":topBar"]');
            return h && cleanText(h.innerText || h.textContent).includes(scopeText);
        });
        if (matchedSec) searchRoot = matchedSec;
    }

    if (rawTarget.startsWith('@')) {
        const byWpId = searchRoot.querySelector('[data-wp-id="' + rawTarget + '"]');
        if (byWpId) { byWpId.click(); return true; }
    }
    if (!scopeText) {
        const direct = document.getElementById(rawTarget);
        if (direct) { direct.click(); return true; }
    }

    const btns = Array.from(searchRoot.querySelectorAll('button, input[type="button"], input[type="submit"], a, [role="button"], [onclick], span[id$="_submitBtn"], span[id$="_saveBtn"], .modal-footer *, .modal-close, [class*="close"], [aria-label*="close" i], p, span'))
        .filter(b => b.offsetWidth > 0 || b.offsetHeight > 0);
    let chosen = btns.find(b => {
        const text = cleanText(b.innerText || b.value || b.title || '');
        const title = cleanText(b.title || b.getAttribute('aria-label') || '');
        return text === lower || title === lower || (b.id && b.id.toLowerCase() === lower);
    });
    if (!chosen) {
        chosen = btns.find(b => {
            const text = cleanText((b.innerText || '') + ' ' + (b.value || '') + ' ' + (b.title || '') + ' ' + (b.id || ''));
            return text.includes(lower);
        });
    }
    if (chosen) {
        chosen.click();
        return true;
    }
    return false;
}"""

