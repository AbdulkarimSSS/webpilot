"""Isolated DOM script for reactive button clicking and dialog dismissing."""

from typing import Final

CLICK_BUTTON_DOM_SCRIPT: Final[str] = """(t) => {
    let rawTarget = (t || '').trim();
    if (!rawTarget) return false;

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
    if (!lower) return false;

    function deepQueryAll(root, selector) {
        const results = [];
        const visited = new Set();
        function walk(node) {
            if (!node || visited.has(node)) return;
            visited.add(node);
            try {
                if (node.querySelectorAll) {
                    const matched = node.querySelectorAll(selector);
                    for (let i = 0; i < matched.length; i++) results.push(matched[i]);
                }
            } catch(e) {}
            try {
                const allNodes = node.querySelectorAll ? node.querySelectorAll('*') : [];
                for (let i = 0; i < allNodes.length; i++) {
                    const sub = allNodes[i];
                    if (sub && sub.shadowRoot) walk(sub.shadowRoot);
                }
            } catch(e) {}
        }
        walk(root || document);
        return results;
    }

    // 0. Priority: Search inside active forms (marked during field population)
    const activeForms = deepQueryAll(document, 'form[data-wp-active-form="true"]');
    if (activeForms.length > 0) {
        for (const frm of activeForms) {
            const btns = deepQueryAll(frm, 'button, input[type="button"], input[type="submit"], a, [role="button"], span[id$="_submitBtn"], span[id$="_saveBtn"]')
                .filter(b => b.offsetWidth > 0 || b.offsetHeight > 0 || (b.getClientRects && b.getClientRects().length > 0));
            let chosen = btns.find(b => {
                const text = cleanText(b.innerText || b.value || b.title || b.getAttribute('aria-label') || '');
                return text === lower || (b.id && b.id.toLowerCase() === lower);
            });
            if (!chosen) {
                chosen = btns.find(b => {
                    const text = cleanText((b.innerText || '') + ' ' + (b.value || '') + ' ' + (b.title || '') + ' ' + (b.id || ''));
                    return text.includes(lower);
                });
            }
            if (!chosen && ['submit', 'apply', 'send', 'save', 'confirm'].includes(lower)) {
                chosen = btns.find(b => (b.getAttribute('type') || '').toLowerCase() === 'submit' || b.tagName === 'BUTTON');
            }
            if (chosen) {
                if (chosen.scrollIntoViewIfNeeded) chosen.scrollIntoViewIfNeeded();
                chosen.click();
                return true;
            }
        }
    }

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

    const btns = deepQueryAll(searchRoot, 'button, input[type="button"], input[type="submit"], a, [role="button"], [onclick], span[id$="_submitBtn"], span[id$="_saveBtn"], .modal-footer *, .modal-close, [class*="close"], [aria-label*="close" i], p, span')
        .filter(b => b.offsetWidth > 0 || b.offsetHeight > 0 || (b.getClientRects && b.getClientRects().length > 0));
    let chosen = btns.find(b => {
        const text = cleanText(b.innerText || b.value || b.title || b.getAttribute('aria-label') || '');
        return text === lower || (b.id && b.id.toLowerCase() === lower);
    });
    if (!chosen) {
        chosen = btns.find(b => {
            const text = cleanText((b.innerText || '') + ' ' + (b.value || '') + ' ' + (b.title || '') + ' ' + (b.id || ''));
            return text.includes(lower);
        });
    }
    if (chosen) {
        if (chosen.scrollIntoViewIfNeeded) chosen.scrollIntoViewIfNeeded();
        chosen.click();
        return true;
    }
    return false;
}"""

