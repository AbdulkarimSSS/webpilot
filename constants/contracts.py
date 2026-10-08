"""Single Source of Truth (SSOT) for data contracts, schema keys, and wire models."""

from typing import Final

# --- Inspection Schema Contract Keys ---
SCHEMA_KEY_TITLE: Final[str] = "title"
SCHEMA_KEY_URL: Final[str] = "url"
SCHEMA_KEY_SECTIONS: Final[str] = "sections"
SCHEMA_KEY_INPUTS: Final[str] = "inputs"
SCHEMA_KEY_DROPDOWNS: Final[str] = "dropdowns"
SCHEMA_KEY_CHOICES: Final[str] = "choices"
SCHEMA_KEY_FILE_UPLOADS: Final[str] = "file_uploads"
SCHEMA_KEY_ALREADY_UPLOADED: Final[str] = "already_uploaded_files"
SCHEMA_KEY_BUTTONS: Final[str] = "buttons"

# --- Field / Element Property Keys ---
FIELD_KEY_ID: Final[str] = "id"
FIELD_KEY_LABEL: Final[str] = "label"
FIELD_KEY_TYPE: Final[str] = "type"
FIELD_KEY_REQUIRED: Final[str] = "required"
FIELD_KEY_VALUE: Final[str] = "value"
FIELD_KEY_TRIGGER_ID: Final[str] = "trigger_id"
FIELD_KEY_SAMPLE_OPTIONS: Final[str] = "sample_options"
FIELD_KEY_OPTIONS_COUNT: Final[str] = "options_count"

# --- Choice Group Property Keys ---
CHOICE_KEY_QUESTION: Final[str] = "question"
CHOICE_KEY_TYPE: Final[str] = "type"
CHOICE_KEY_REQUIRED: Final[str] = "required"
CHOICE_KEY_OPTIONS: Final[str] = "options"
CHOICE_KEY_SELECTED: Final[str] = "selected"

# --- Action Button Property Keys ---
BUTTON_KEY_ID: Final[str] = "id"
BUTTON_KEY_TEXT: Final[str] = "text"
BUTTON_KEY_ACTION: Final[str] = "action"

# --- Widget Type Identifiers ---
WIDGET_TYPE_TEXT: Final[str] = "text"
WIDGET_TYPE_SELECT: Final[str] = "select"
WIDGET_TYPE_PICKLIST: Final[str] = "picklist"
WIDGET_TYPE_RADIO: Final[str] = "radio"
WIDGET_TYPE_CHECKBOX: Final[str] = "checkbox"
WIDGET_TYPE_CUSTOM_RADIO: Final[str] = "custom_radio"
WIDGET_TYPE_BUTTON: Final[str] = "button"
BUTTON_ACTION_DEFAULT: Final[str] = "action"

# --- Reactive Action Outcome Keys ---
OUTCOME_KEY_SUCCESS: Final[str] = "success"
OUTCOME_KEY_TARGET: Final[str] = "target"
OUTCOME_KEY_REDIRECTED: Final[str] = "redirected"
OUTCOME_KEY_NEW_WINDOW: Final[str] = "new_window"
OUTCOME_KEY_NEW_URL: Final[str] = "new_url"
OUTCOME_KEY_MODAL_OPENED: Final[str] = "modal_opened"
OUTCOME_KEY_MODAL_TEXT: Final[str] = "modal_text"
OUTCOME_KEY_NEW_INPUTS_COUNT: Final[str] = "new_inputs_count"
OUTCOME_KEY_SCHEMA: Final[str] = "schema"
OUTCOME_KEY_ALERTS: Final[str] = "alerts"

# --- Fill Summary Keys ---
SUMMARY_KEY_CONFIRMED: Final[str] = "confirmed"
SUMMARY_KEY_UNCONFIRMED: Final[str] = "unconfirmed"
SUMMARY_KEY_FAILED: Final[str] = "failed"

# --- Contract Key Sets ---
SCHEMA_KEYS: Final[set] = {
    SCHEMA_KEY_TITLE,
    SCHEMA_KEY_URL,
    SCHEMA_KEY_SECTIONS,
    SCHEMA_KEY_INPUTS,
    SCHEMA_KEY_DROPDOWNS,
    SCHEMA_KEY_CHOICES,
    SCHEMA_KEY_FILE_UPLOADS,
    SCHEMA_KEY_ALREADY_UPLOADED,
    SCHEMA_KEY_BUTTONS,
}

OUTCOME_KEYS: Final[set] = {
    OUTCOME_KEY_SUCCESS,
    OUTCOME_KEY_TARGET,
    OUTCOME_KEY_REDIRECTED,
    OUTCOME_KEY_NEW_WINDOW,
    OUTCOME_KEY_NEW_URL,
    OUTCOME_KEY_MODAL_OPENED,
    OUTCOME_KEY_MODAL_TEXT,
    OUTCOME_KEY_NEW_INPUTS_COUNT,
    OUTCOME_KEY_SCHEMA,
    OUTCOME_KEY_ALERTS,
}

SUMMARY_KEYS: Final[set] = {
    SUMMARY_KEY_CONFIRMED,
    SUMMARY_KEY_UNCONFIRMED,
    SUMMARY_KEY_FAILED,
}
