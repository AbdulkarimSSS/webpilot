"""Isolated DOM scripts for page lifecycle readiness and accordion section expansion."""

from typing import Final

CHECK_FORM_LOADING_SCRIPT: Final[str] = """() => {
    const text = (document.body && document.body.innerText) ? document.body.innerText.trim() : '';
    if (!text || text === 'Loading...') return true;
    const hasFormElements = document.querySelectorAll('input:not([type="hidden"]), select, textarea, .rcmFormSection, [role="combobox"], button[id*="expandAll" i]').length > 0;
    if (!hasFormElements && (text.includes('Loading...') || document.querySelector('.loading, .spinner, [aria-busy="true"]'))) return true;
    return false;
}"""

EXPAND_ALL_SECTIONS_SCRIPT: Final[str] = """() => {
    let count = 0;
    // 1. Check for master 'Expand all' buttons (SuccessFactors, Workday, Taleo, etc.)
    const masterBtns = Array.from(document.querySelectorAll('button, a, [role="button"], span')).filter(el => {
        const id = (el.id || '').toLowerCase();
        const text = (el.innerText || el.textContent || '').trim().toLowerCase();
        return id.includes('expandallsections') || id.includes('expandall') || text === 'expand all' || text.includes('expand all sections');
    });
    for (let mb of masterBtns) {
        try {
            mb.click();
            count++;
        } catch (e) {}
    }

    // 2. Expand individual form sections and accordions
    const candidateNodes = Array.from(document.querySelectorAll(
        '.rcmFormSection, [class*="rcmFormSection"], [class*="accordion"], .accordion-item, details, .rcmFormSectionTopBar, [id$=":topBar"], button[class*="topBar"]'
    ));

    const clickedSet = new Set();

    for (let s of candidateNodes) {
        if (s.tagName && s.tagName.toLowerCase() === 'details') {
            if (!s.hasAttribute('open')) {
                s.setAttribute('open', '');
                count++;
            }
            continue;
        }

        let btn = null;
        if (s.matches && s.matches('button, [role="button"], .rcmFormSectionTopBar, [id$=":topBar"], .accordion-button')) {
            btn = s;
        } else {
            btn = s.querySelector('button.rcmFormSectionTopBar, .rcmFormSectionTopBar, [id$=":topBar"], [aria-expanded="false"], .accordion-button.collapsed, button, [role="button"]');
        }

        if (!btn || clickedSet.has(btn)) continue;

        const content = (s.matches && s.matches('.rcmFormSectionTopBar, [id$=":topBar"]'))
            ? (s.parentElement ? s.parentElement.querySelector('.sectionContent, [class*="sectionContent"], .accordion-collapse') : null)
            : s.querySelector('.sectionContent, [class*="sectionContent"], .accordion-collapse:not(.show)');

        const isClosed = (btn.getAttribute('aria-expanded') === 'false') ||
                         (btn.classList.contains('collapsed')) ||
                         (content && (content.classList.contains('sectionContentClosed') || content.style.display === 'none'));

        if (isClosed) {
            try {
                btn.click();
                clickedSet.add(btn);
                count++;
            } catch (e) {}
        }
    }
    return count;
}"""
