"""Target descriptor grammar and hierarchical scoping parser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class TargetDescriptor:
    """Parsed components of a target element descriptor."""
    type_hint: Optional[str]
    clean_target: str
    scoped_parent: Optional[str]

    def to_tuple(self) -> Tuple[Optional[str], str, Optional[str]]:
        return self.type_hint, self.clean_target, self.scoped_parent


class TargetDescriptorParser:
    """Parses type hint prefixes and hierarchical scoping from target strings.

    Examples:
        'text:First Name' -> ('text', 'First Name', None)
        'picklist:Education > Degree' -> ('picklist', 'Degree', 'Education')
        'Education > Degree' -> (None, 'Degree', 'Education')
        '@fld-1' -> (None, '@fld-1', None)
    """

    KNOWN_TYPES = (
        "text",
        "picklist",
        "select",
        "combobox",
        "radio",
        "checkbox",
        "choice",
        "input",
        "textarea",
    )

    @classmethod
    def parse(cls, target: str) -> TargetDescriptor:
        """Parses target descriptor into (type_hint, clean_target, scoped_parent)."""
        raw = target.strip()
        type_hint: Optional[str] = None
        scoped_parent: Optional[str] = None

        if ":" in raw and not raw.startswith("@"):
            prefix, rest = raw.split(":", 1)
            if prefix.lower().strip() in cls.KNOWN_TYPES:
                type_hint = prefix.lower().strip()
                raw = rest.strip()

        # 1. Explicit safe prefix: 'scope:Section:Field' or 'section:Section:Field'
        if raw.lower().startswith(("scope:", "section:")):
            parts = raw.split(":", 2)
            if len(parts) == 3:
                scoped_parent = parts[1].strip()
                raw = parts[2].strip()
            elif len(parts) == 2:
                scoped_parent = parts[1].strip()
                raw = parts[1].strip()

        # 2. Section LocalID prefix: '@sec-1:Field'
        elif raw.startswith("@sec-") and ":" in raw:
            parts = raw.split(":", 1)
            scoped_parent = parts[0].strip()
            raw = parts[1].strip()

        # 3. Fallback divider support
        elif " > " in raw:
            parts = [p.strip() for p in raw.split(" > ")]
            if len(parts) >= 2:
                scoped_parent = " > ".join(parts[:-1])
                raw = parts[-1]
        elif ">" in raw:
            parts = [p.strip() for p in raw.split(">")]
            if len(parts) >= 2:
                scoped_parent = ">".join(parts[:-1])
                raw = parts[-1]

        return TargetDescriptor(
            type_hint=type_hint,
            clean_target=raw,
            scoped_parent=scoped_parent,
        )
