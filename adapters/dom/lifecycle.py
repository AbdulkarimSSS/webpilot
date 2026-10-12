"""Isolated DOM scripts for page lifecycle readiness and accordion section expansion."""

from typing import Final

CHECK_FORM_LOADING_SCRIPT: Final[str] = (
    "() => document.body.innerText.trim() === 'Loading...' || document.body.innerText.trim() === ''"
)

EXPAND_ALL_SECTIONS_SCRIPT: Final[str] = """() => {
    let count = 0;
    // 1. Check for master 'Expand all' buttons (SuccessFactors, Workday, Taleo, etc.)
    const masterBtns = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(el => {
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
    const sections = Array.from(document.querySelectorAll('.rcmFormSection, [class*="rcmFormSection"], [class*="accordion"], .accordion-item, details:not([open])'));
    for (let s of sections) {
        if (s.tagName && s.tagName.toLowerCase() === 'details') {
            s.setAttribute('open', '');
            count++;
            continue;
        }
        const btn = s.querySelector('button.rcmFormSectionTopBar, .rcmFormSectionTopBar, [aria-expanded="false"], .accordion-button.collapsed');
        const content = s.querySelector('.sectionContent, [class*="sectionContent"], .accordion-collapse:not(.show)');
        const isClosed = (btn && btn.getAttribute('aria-expanded') === 'false') ||
                         (content && content.classList.contains('sectionContentClosed')) ||
                         (btn && btn.classList.contains('collapsed'));
        if (isClosed && btn) {
            btn.click();
            count++;
        }
    }
    return count;
}"""
