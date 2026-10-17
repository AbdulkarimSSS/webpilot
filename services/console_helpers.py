"""Console helper wrapper and evaluation utilities for WebPilot.

Injects browser console-like shortcuts ($0, $(), $$(), $x(), copy()) into
evaluated JavaScript expressions, making agent interactions ergonomic and familiar.
"""

from __future__ import annotations

from typing import Any, Optional

XPATH_SNAPSHOT_TYPE = "XPathResult.ORDERED_NODE_SNAPSHOT_TYPE"
WRAPPER_INDENT = "  "


class InvalidUserCodeError(TypeError):
    """Raised when user JavaScript expression is invalid or empty."""
    pass


def validate_user_code(user_code: Any) -> str:
    """Validates that userCode is a non-empty string."""
    if not isinstance(user_code, str) or not user_code.strip():
        raise InvalidUserCodeError(f"wrap_with_console_helpers: expected non-empty string, got {type(user_code).__name__}")
    return user_code


def build_prelude_source() -> str:
    """Builds JavaScript source string defining $(), $$(), $x(), $0, and copy() helpers."""
    lines = [
        "const toArray = (list) => Array.from(list);",
        "const $ = (selector, root = document) => root.querySelector(selector);",
        "const $$ = (selector, root = document) => toArray(root.querySelectorAll(selector));",
        "const $x = (xpath, root = document) => {",
        f"  const snap = document.evaluate(xpath, root, null, {XPATH_SNAPSHOT_TYPE}, null);",
        "  return Array.from({ length: snap.snapshotLength }, (_, i) => snap.snapshotItem(i));",
        "};",
        "const $0 = document.activeElement || document.body;",
        "const copy = (val) => {",
        "  const str = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val);",
        "  if (navigator && navigator.clipboard && navigator.clipboard.writeText) {",
        "    navigator.clipboard.writeText(str).catch(() => {});",
        "  }",
        "  return str;",
        "};",
    ]
    return "\n".join(WRAPPER_INDENT + line for line in lines)


def wrap_with_console_helpers(user_code: str) -> str:
    """Wraps user-provided JavaScript with console helpers ($0, $, $$, $x, copy).

    Prevents trailing comments from swallowing the closing paren by adding a trailing newline.
    """
    code = validate_user_code(user_code)
    prelude = build_prelude_source()
    return f"(() => {{\n{prelude}\n{WRAPPER_INDENT}return ({code}\n{WRAPPER_INDENT});\n}})()"
