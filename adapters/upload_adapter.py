"""Document and resume attachment adapter."""

from __future__ import annotations

import os
from playwright.sync_api import Page
from adapters.base import UploadAdapterProtocol
from constants.timeouts import PAUSE_UPLOAD_DIRECT_MS, PAUSE_UPLOAD_CHOOSER_MS
from core.exceptions import DocumentUploadError


class UploadAdapter(UploadAdapterProtocol):
    """Handles multi-heuristic document attachments across ATS platforms."""

    def __init__(self, page: Page):
        self.page = page

    def upload_document(self, file_path: str, document_type_keyword: str = "") -> bool:
        """Attaches a local document to the form using direct input or file chooser dialogs."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Target document not found: {file_path}")

        print(f"Uploading document '{file_path}' (Keyword: '{document_type_keyword}')...")

        # 1. Native input[type="file"]
        file_inputs = self.page.locator("input[type='file']").all()
        if file_inputs:
            target_fi = file_inputs[-1]
            if document_type_keyword:
                for fi in file_inputs:
                    lbl = self.page.evaluate(
                        "(el) => el.closest('div, tr')?.innerText || ''",
                        fi.element_handle()
                    )
                    if document_type_keyword.lower() in lbl.lower():
                        target_fi = fi
                        break
            target_fi.set_input_files(file_path)
            self.page.wait_for_timeout(PAUSE_UPLOAD_DIRECT_MS)
            print("File set directly on file input.")
            return True

        # 2. Custom ARIA / ATS Trigger Button
        custom_trigger = self.page.evaluate("""(kw) => {
            const triggers = Array.from(document.querySelectorAll(
                '[id*="attach"], [id*="upload"], [id*="Add"], [title*="Add"], button, a'
            )).filter(el => {
                const t = (el.innerText || el.title || el.id || '').toLowerCase();
                if (kw && !t.includes(kw.toLowerCase())) return false;
                return t.includes('add a document') || t.includes('attach') || t.includes('upload');
            });
            return triggers[0] ? triggers[0].id : null;
        }""", document_type_keyword)

        if custom_trigger:
            print(f"Triggering upload via custom button ID: {custom_trigger}...")
            with self.page.expect_file_chooser(timeout=10000) as fc_info:
                self.page.locator(f'[id="{custom_trigger}"]').click(force=True)
            file_chooser = fc_info.value
            file_chooser.set_files(file_path)
            self.page.wait_for_timeout(PAUSE_UPLOAD_CHOOSER_MS)
            return True

        # 3. SuccessFactors JUIC framework fallback
        try:
            with self.page.expect_file_chooser(timeout=5000) as fc_info:
                self.page.evaluate(
                    "() => { if (window.juic && window.juic.fire) juic.fire('48:', 'action', { type: 'click' }); }"
                )
            file_chooser = fc_info.value
            file_chooser.set_files(file_path)
            self.page.wait_for_timeout(PAUSE_UPLOAD_CHOOSER_MS)
            return True
        except Exception:
            pass

        return False
