"""Form validation and error banner inspection."""

from typing import List
from playwright.sync_api import Page
from constants.selectors import SELECTOR_VALIDATION_ERRORS

class FormValidator:
    """Inspects the active DOM for validation notices, errors, and alerts."""

    def __init__(self, page: Page):
        self.page = page

    def get_validation_errors(self) -> List[str]:
        """Collects error alerts, validation messages, or red warning texts currently shown."""
        if self.page is None:
            return []

        errors = self.page.evaluate("""(selector) => {
            const errorNodes = Array.from(document.querySelectorAll(selector));
            const texts = errorNodes.map(e => e.innerText.trim()).filter(t => t.length > 0);

            // Also inspect lines starting with error glyphs
            const bodyLines = document.body.innerText.split('\\n').map(l => l.trim());
            const errLines = bodyLines.filter(l => l.includes('is required') || l.includes('Please correct the errors'));
            return Array.from(new Set([...texts, ...errLines]));
        }""", SELECTOR_VALIDATION_ERRORS)

        return list(errors)
