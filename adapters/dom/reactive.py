"""Isolated DOM script for reactive button clicking and dialog dismissing."""

from typing import Final

CLICK_BUTTON_DOM_SCRIPT: Final[str] = """(t) => {
    const lower = (t || '').toLowerCase().trim();
    if (t.startsWith('@')) {
        const byWpId = document.querySelector('[data-wp-id="' + t + '"]');
        if (byWpId) { byWpId.click(); return true; }
    }
    const direct = document.getElementById(t);
    if (direct) { direct.click(); return true; }

    const btns = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], a, [role="button"], span[id$="_submitBtn"], span[id$="_saveBtn"], .modal-footer *, .modal-close, [class*="close"], [aria-label*="close" i], p, span'));
    let chosen = btns.find(b => {
        const text = (b.innerText || b.value || b.title || '').trim().toLowerCase();
        return text === lower || (b.id && b.id.toLowerCase() === lower);
    });
    if (!chosen) {
        chosen = btns.find(b => {
            const text = (b.innerText || b.value || b.title || b.id || '').trim().toLowerCase();
            return text.includes(lower);
        });
    }
    if (chosen) {
        chosen.click();
        return true;
    }
    return false;
}"""

