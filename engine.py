"""Universal Form Engine Facade.

Maintains 100% backwards-compatible external behavior while delegating to
cohesive domain services and adapters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Browser, BrowserContext, Page

from adapters.browser_adapter import BrowserAdapter
from adapters.upload_adapter import UploadAdapter
from config.settings import Settings, get_settings, load_device_profile
from core.models import DeviceProfile
from services.auth_navigation_service import AuthNavigationService
from services.field_interaction_service import FieldInteractionService
from services.form_filler_service import FormFillerService
from services.inspection_formatter_service import InspectionFormatterService
from services.inspection_service import InspectionService
from services.reactive_interaction_service import ReactiveInteractionService
from validators.form_validator import FormValidator


class UniversalFormEngine:
    """Universal Form Engine facade coordinating browser lifecycle, inspection, and interaction services."""

    def __init__(
        self,
        headless: Optional[bool] = None,
        settings: Optional[Settings] = None,
        device_profile: Optional[DeviceProfile] = None,
        viewport: Optional[dict] = None,
        user_agent: Optional[str] = None,
    ):
        self.settings = settings or get_settings()
        self.device_profile = device_profile or load_device_profile()

        if viewport:
            self.device_profile.viewport_width = viewport.get("width", self.device_profile.viewport_width)
            self.device_profile.viewport_height = viewport.get("height", self.device_profile.viewport_height)
        if user_agent:
            self.device_profile.user_agent = user_agent

        self.headless = headless if headless is not None else self.settings.headless
        self.viewport = self.device_profile.viewport_dict()
        self.user_agent = self.device_profile.user_agent

        self.browser_adapter = BrowserAdapter(
            headless=self.headless,
            settings=self.settings,
            device_profile=self.device_profile,
        )

        # Service instances initialized upon start()
        self.auth_service: Optional[AuthNavigationService] = None
        self.inspection_service: Optional[InspectionService] = None
        self.field_service: Optional[FieldInteractionService] = None
        self.filler_service: Optional[FormFillerService] = None
        self.upload_adapter: Optional[UploadAdapter] = None
        self.validator: Optional[FormValidator] = None
        self.reactive_service: Optional[ReactiveInteractionService] = None

    @property
    def browser(self) -> Optional[Browser]:
        """Underlying Playwright Browser."""
        return self.browser_adapter.browser

    @property
    def context(self) -> Optional[BrowserContext]:
        """Active Playwright BrowserContext."""
        return self.browser_adapter.context

    @property
    def page(self) -> Optional[Page]:
        """Active Playwright Page."""
        return self.browser_adapter.page

    @page.setter
    def page(self, p: Page) -> None:
        self.browser_adapter.page = p
        if self._services_ready():
            self._bind_services(p)

    def _services_ready(self) -> bool:
        return self.auth_service is not None

    def _bind_services(self, active_page: Page) -> None:
        """Binds active page to services and adapters."""
        ctx = self.context
        assert ctx is not None
        self.auth_service = AuthNavigationService(active_page, ctx)
        self.inspection_service = InspectionService(active_page)
        self.field_service = FieldInteractionService(active_page)
        self.filler_service = FormFillerService(active_page, self.field_service)
        self.upload_adapter = UploadAdapter(active_page)
        self.validator = FormValidator(active_page)
        self.reactive_service = ReactiveInteractionService(
            page=active_page,
            context=ctx,
            inspection_service=self.inspection_service,
            form_validator=self.validator,
            on_active_page_change=self._on_active_page_change,
        )

    def _on_active_page_change(self, new_page: Page) -> None:
        self.browser_adapter.page = new_page
        self._bind_services(new_page)

    def start(self, cookies_path: Optional[str] = None) -> None:
        """Starts Playwright browser instance, initializes context, and prepares services."""
        self.browser_adapter.start(cookies_path=cookies_path)
        assert self.page is not None
        self._bind_services(self.page)

    def stop(self) -> None:
        """Closes browser context and Playwright instance."""
        self.browser_adapter.stop()

    def navigate(self, url: str, wait_timeout: Optional[int] = None) -> None:
        """Navigates to URL and waits for DOM content loaded."""
        self.browser_adapter.navigate(url=url, wait_timeout=wait_timeout)

    def handle_login_if_needed(self, email: str, password: str, cookies_save_path: Optional[str] = None) -> bool:
        """Detects if page is a login/sign-in page and completes authentication automatically."""
        assert self.auth_service is not None, "Engine not started."
        return self.auth_service.handle_login_if_needed(email, password, cookies_save_path)

    def bypass_job_landing_portal(self) -> bool:
        """Generic helper: Clicks Apply Now on portal landing pages to enter ATS application."""
        assert self.auth_service is not None, "Engine not started."
        res = self.auth_service.bypass_job_landing_portal()
        if self.page != self.auth_service.page:
            self.page = self.auth_service.page
        return res

    def wait_for_form_ready(self, timeout_ms: Optional[int] = None) -> None:
        """Waits for form elements to be rendered in DOM, dismissing 'Loading...' state."""
        assert self.auth_service is not None, "Engine not started."
        effective_timeout = timeout_ms if timeout_ms is not None else self.settings.form_ready_timeout_ms
        self.auth_service.wait_for_form_ready(timeout_ms=effective_timeout)

    def expand_all_sections(self) -> int:
        """Safely expands any collapsed form sections without toggling already-open ones."""
        assert self.auth_service is not None, "Engine not started."
        return self.auth_service.expand_all_sections(wait_ms=self.settings.expand_section_wait_ms)

    def fill_form_sequential(self, field_mappings: List[Tuple[str, Any]]) -> Dict[str, List[Tuple[str, Any]]]:
        """Universal sequential form filler (section-by-section + global fallback)."""
        assert self.filler_service is not None, "Engine not started."
        return self.filler_service.fill_form_sequential(field_mappings)

    def inspect(self, unpack_options: bool = True) -> Dict[str, Any]:
        """Deep inspection of the active page form components and schema."""
        assert self.auth_service is not None and self.inspection_service is not None, "Engine not started."
        self.wait_for_form_ready()
        self.expand_all_sections()
        return self.inspection_service.inspect(unpack_options=unpack_options)

    def format_inspection_summary(self, data: Dict[str, Any]) -> str:
        """Returns a concise, human-readable summary of the inspected form."""
        return InspectionFormatterService.format_summary(data)

    def set_field(self, target_identifier: str, value: Any) -> bool:
        """Sets form field value across text, picklist, radio, checkbox widgets."""
        assert self.field_service is not None, "Engine not started."
        return self.field_service.set_field(target_identifier, value)

    def _playwright_click_fallback(self, target: str, value: Any) -> bool:
        """Fallback setter using Playwright native locators (click / fill)."""
        assert self.field_service is not None, "Engine not started."
        return self.field_service._playwright_click_fallback(target, value)

    def verify_field_value(self, target: str, expected: Any) -> bool:
        """Reads back current DOM value of field and checks if it matches expected."""
        assert self.field_service is not None, "Engine not started."
        return self.field_service.verify_field_value(target, expected)

    def upload_document(self, file_path: str, document_type_keyword: str = "") -> bool:
        """Universally attaches a document to file inputs or custom ATS chooser triggers."""
        assert self.upload_adapter is not None, "Engine not started."
        return self.upload_adapter.upload_document(file_path, document_type_keyword)

    def click_button(self, button_text_or_purpose: str) -> Dict[str, Any]:
        """Intelligently clicks a button/link and monitors reactive environmental mutations."""
        assert self.reactive_service is not None, "Engine not started."
        outcome = self.reactive_service.click_button(button_text_or_purpose)
        if outcome.get("new_window") and self.page != self.reactive_service.page:
            self.page = self.reactive_service.page
        return outcome

    def get_validation_errors(self) -> List[str]:
        """Collects any error alerts, validation messages, or warning texts currently shown."""
        assert self.validator is not None, "Engine not started."
        return self.validator.get_validation_errors()

    def capture_screenshot(self, output_path: str, full_page: bool = False) -> None:
        """Saves a screenshot of the current page."""
        self.browser_adapter.capture_screenshot(output_path=output_path, full_page=full_page)
