"""CSS and XPath selector constants for form elements and framework widgets."""

from typing import Final

# Form section and accordion toggle selectors
SELECTOR_SECTION_BUTTON: Final[str] = "button.rcmFormSectionTopBar, .rcmFormSectionTopBar"
SELECTOR_SECTION_CONTAINER: Final[str] = ".rcmFormSection, [class*='rcmFormSection']"
SELECTOR_SECTION_CONTENT: Final[str] = ".sectionContent, [class*='sectionContent']"

# Job portal landing transition selectors
SELECTOR_PORTAL_DROPDOWN: Final[str] = "button.dropdown-toggle, .dropdown-toggle, [data-toggle='dropdown']"
SELECTOR_PORTAL_APPLY_BUTTON: Final[str] = ".dialogApplyBtn"

# File input and upload trigger selectors
SELECTOR_FILE_INPUT_GENERIC: Final[str] = "input[type='file']"
SELECTOR_CUSTOM_UPLOAD_TRIGGERS: Final[str] = (
    "input[type='file'], .sfFileUpload, .fileUploadWrapper, [role='button'][id*='_attach']"
)

# Enterprise picklist / Combobox selectors
SELECTOR_PICKLIST_INPUTS: Final[str] = "input[role='combobox'], input[id$=':_input']"
SELECTOR_MODAL_DIALOGS: Final[str] = ".modal:visible, [role='dialog']:visible, .dialog:visible, .pop-up:visible"

# Error banners and validation notice selectors
SELECTOR_VALIDATION_ERRORS: Final[str] = (
    ".alert-danger, .error, .errorMessage, .sf-error, [role='alert'], .validation-summary-errors, .has-error"
)
