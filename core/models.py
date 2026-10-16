"""Shared domain Transfer Objects (DTOs) and data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from core.exceptions import ValidationError


@dataclass
class ProxyConfig:
    """Network proxy configuration loaded from settings."""
    server: str
    username: Optional[str] = None
    password: Optional[str] = None

    def to_playwright_dict(self) -> Dict[str, str]:
        """Convert to Playwright-compatible proxy dictionary."""
        d: Dict[str, str] = {"server": self.server}
        if self.username:
            d["username"] = self.username
        if self.password:
            d["password"] = self.password
        return d


@dataclass
class DeviceProfile:
    """Device & browser profile parameters for browser context emulation."""
    device_name: str
    user_agent: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
    locale: str = "en-US"
    timezone_id: str = "UTC"
    geolocation_latitude: Optional[float] = None
    geolocation_longitude: Optional[float] = None
    geolocation_accuracy: Optional[float] = None
    permissions: List[str] = field(default_factory=list)
    platform: str = "Win32"
    vendor: str = "Google Inc."

    def viewport_dict(self) -> Dict[str, int]:
        """Returns the viewport dimensions dictionary."""
        return {"width": self.viewport_width, "height": self.viewport_height}

    def geolocation_dict(self) -> Optional[Dict[str, float]]:
        """Returns geolocation dictionary if valid coordinates are present."""
        if self.geolocation_latitude is not None and self.geolocation_longitude is not None:
            return {
                "latitude": float(self.geolocation_latitude),
                "longitude": float(self.geolocation_longitude),
                "accuracy": float(self.geolocation_accuracy or 10.0),
            }
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceProfile":
        """Instantiate a DeviceProfile strictly from parsed dictionary data."""
        if not isinstance(data, dict):
            raise ValidationError(f"Expected dict for DeviceProfile, got {type(data).__name__}")

        viewport = data.get("viewport") or {}
        vp_width = data.get("viewport_width") or viewport.get("width")
        vp_height = data.get("viewport_height") or viewport.get("height")

        geo = data.get("geolocation") or {}
        geo_lat = data.get("geolocation_latitude", geo.get("latitude"))
        geo_lon = data.get("geolocation_longitude", geo.get("longitude"))
        geo_acc = data.get("geolocation_accuracy", geo.get("accuracy"))

        return cls(
            device_name=str(data.get("device_name", "")),
            user_agent=str(data.get("user_agent", "")),
            viewport_width=int(vp_width) if vp_width is not None else 0,
            viewport_height=int(vp_height) if vp_height is not None else 0,
            device_scale_factor=float(data.get("device_scale_factor", 1.0)),
            is_mobile=bool(data.get("is_mobile", False)),
            has_touch=bool(data.get("has_touch", False)),
            locale=str(data.get("locale", "en-US")),
            timezone_id=str(data.get("timezone_id", "UTC")),
            geolocation_latitude=float(geo_lat) if geo_lat is not None else None,
            geolocation_longitude=float(geo_lon) if geo_lon is not None else None,
            geolocation_accuracy=float(geo_acc) if geo_acc is not None else None,
            permissions=list(data.get("permissions", [])),
            platform=str(data.get("platform", "Win32")),
            vendor=str(data.get("vendor", "Google Inc.")),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert DeviceProfile to serializable dictionary."""
        d: Dict[str, Any] = {
            "device_name": self.device_name,
            "user_agent": self.user_agent,
            "viewport": self.viewport_dict(),
            "device_scale_factor": self.device_scale_factor,
            "is_mobile": self.is_mobile,
            "has_touch": self.has_touch,
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "permissions": self.permissions,
            "platform": self.platform,
            "vendor": self.vendor,
        }
        geo = self.geolocation_dict()
        if geo:
            d["geolocation"] = geo
        return d


@dataclass
class InputField:
    """Inspected text or numeric input element."""
    id: str
    label: str
    type: str = "text"
    required: bool = False
    value: str = ""
    local_id: str = ""


@dataclass
class DropdownField:
    """Inspected select dropdown or combobox picklist."""
    id: str
    label: str
    type: str = "select"
    required: bool = False
    value: str = ""
    trigger_id: str = ""
    sample_options: List[str] = field(default_factory=list)
    options_count: int = 0
    local_id: str = ""


@dataclass
class ChoiceGroup:
    """Inspected radio or checkbox group for a question."""
    question: str
    type: str = "radio"
    required: bool = False
    options: List[str] = field(default_factory=list)
    selected: Optional[str] = None
    local_id: str = ""


@dataclass
class FileUploadField:
    """Inspected file upload zone or attachment input."""
    id: str
    label: str
    required: bool = False
    local_id: str = ""


@dataclass
class ActionButton:
    """Inspected form action button."""
    id: str
    text: str
    action: str = "action"
    local_id: str = ""
    scope: str = ""


@dataclass
class FormSection:
    """Inspected form section or accordion."""
    title: str = ""
    label: str = ""
    state: str = "OPEN"
    local_id: str = ""
    id: str = ""
    trigger_id: str = ""
    trigger_local_id: str = ""
    is_collapsible: bool = False
    fields_count: int = 0
    total_fields: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "label": self.label,
            "state": self.state,
            "local_id": self.local_id,
            "id": self.id,
            "trigger_id": self.trigger_id,
            "trigger_local_id": self.trigger_local_id,
            "is_collapsible": self.is_collapsible,
            "fields_count": self.fields_count,
            "total_fields": self.total_fields,
        }


@dataclass
class InspectionResult:
    """Consolidated form inspection schema."""
    title: str = ""
    url: str = ""
    sections: List[Union[str, FormSection, Dict[str, Any]]] = field(default_factory=list)
    inputs: List[InputField] = field(default_factory=list)
    dropdowns: List[DropdownField] = field(default_factory=list)
    choices: List[ChoiceGroup] = field(default_factory=list)
    file_uploads: List[FileUploadField] = field(default_factory=list)
    already_uploaded_files: List[str] = field(default_factory=list)
    buttons: List[ActionButton] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary matching legacy schema format."""
        sec_list = []
        for s in self.sections:
            if hasattr(s, "to_dict"):
                sec_list.append(s.to_dict())
            elif is_dataclass(s):
                sec_list.append(asdict(s))
            else:
                sec_list.append(s)
        return {
            "title": self.title,
            "url": self.url,
            "sections": sec_list,
            "inputs": [vars(i) for i in self.inputs],
            "dropdowns": [vars(d) for d in self.dropdowns],
            "choices": [vars(c) for c in self.choices],
            "file_uploads": [vars(f) for f in self.file_uploads],
            "already_uploaded_files": self.already_uploaded_files,
            "buttons": [vars(b) for b in self.buttons],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InspectionResult":
        """Instantiate DTO from raw inspection dictionary."""
        raw_sections = data.get("sections", [])
        parsed_sections = []
        for s in raw_sections:
            if isinstance(s, dict):
                parsed_sections.append(
                    FormSection(
                        title=s.get("title", s.get("label", "")),
                        label=s.get("label", s.get("title", "")),
                        state=s.get("state", "OPEN"),
                        local_id=s.get("local_id", ""),
                        id=s.get("id", ""),
                        trigger_id=s.get("trigger_id", ""),
                        trigger_local_id=s.get("trigger_local_id", ""),
                        is_collapsible=s.get("is_collapsible", False),
                        fields_count=s.get("fields_count", 0),
                        total_fields=s.get("total_fields", 0),
                    )
                )
            else:
                parsed_sections.append(s)
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            sections=parsed_sections,
            inputs=[InputField(**i) if isinstance(i, dict) else i for i in data.get("inputs", [])],
            dropdowns=[DropdownField(**d) if isinstance(d, dict) else d for d in data.get("dropdowns", [])],
            choices=[ChoiceGroup(**c) if isinstance(c, dict) else c for c in data.get("choices", [])],
            file_uploads=[FileUploadField(**f) if isinstance(f, dict) else f for f in data.get("file_uploads", [])],
            already_uploaded_files=list(data.get("already_uploaded_files", [])),
            buttons=[ActionButton(**b) if isinstance(b, dict) else b for b in data.get("buttons", [])],
        )


@dataclass
class FillSummary:
    """Summary record for batch sequential form filling."""
    confirmed: List[Tuple[str, Any]] = field(default_factory=list)
    unconfirmed: List[Tuple[str, Any]] = field(default_factory=list)
    failed: List[Tuple[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, List[Tuple[str, Any]]]:
        """Return standard dictionary format matching legacy API."""
        return {
            "confirmed": list(self.confirmed),
            "unconfirmed": list(self.unconfirmed),
            "failed": list(self.failed),
        }


@dataclass
class ReactiveClickOutcome:
    """Outcome and reactive environment mutations triggered by a button press."""
    success: bool
    target: str
    redirected: bool = False
    new_window: bool = False
    new_url: Optional[str] = None
    modal_opened: bool = False
    modal_text: str = ""
    new_inputs_count: int = 0
    schema: Optional[Dict[str, Any]] = None
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary format matching legacy API."""
        return {
            "success": self.success,
            "target": self.target,
            "redirected": self.redirected,
            "new_window": self.new_window,
            "new_url": self.new_url,
            "modal_opened": self.modal_opened,
            "modal_text": self.modal_text,
            "new_inputs_count": self.new_inputs_count,
            "schema": self.schema,
            "alerts": self.alerts,
        }


@dataclass
class ApplyExecutionResult:
    """Structured result returned upon completion of an apply flow."""
    confirmed_fields: List[Tuple[str, Any]] = field(default_factory=list)
    unconfirmed_fields: List[Tuple[str, Any]] = field(default_factory=list)
    failed_fields: List[Tuple[str, Any]] = field(default_factory=list)
    final_url: str = ""
    validation_errors: List[str] = field(default_factory=list)
    submitted: bool = False
    confirmation_screenshot: Optional[str] = None

    @property
    def overall_success(self) -> bool:
        """Physical honesty contract: success requires zero failed fields, zero unconfirmed fields, and zero validation errors."""
        return (
            len(self.failed_fields) == 0
            and len(self.unconfirmed_fields) == 0
            and len(self.validation_errors) == 0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching standard serialization."""
        return {
            "overall_success": self.overall_success,
            "confirmed_fields": list(self.confirmed_fields),
            "unconfirmed_fields": list(self.unconfirmed_fields),
            "failed_fields": list(self.failed_fields),
            "final_url": self.final_url,
            "validation_errors": list(self.validation_errors),
            "submitted": self.submitted,
            "confirmation_screenshot": self.confirmation_screenshot,
        }
