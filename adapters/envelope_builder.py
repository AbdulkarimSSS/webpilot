"""Browser context options envelope builder for Playwright."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from config.settings import Settings, get_settings, load_device_profile
from core.exceptions import ConfigurationError
from core.models import DeviceProfile


class BrowserContextEnvelopeBuilder:
    """Constructs the browser context options envelope for Playwright.

    Reads strictly from a DeviceProfile and optional Settings model.
    Never injects hardcoded string literals for device details, user agent,
    or viewport dimensions. Missing required attributes trigger a fallback to
    the verified configuration file, or raise a descriptive ConfigurationError.
    """

    REQUIRED_ATTRIBUTES = ("user_agent", "viewport_width", "viewport_height")

    def __init__(
        self,
        profile: Optional[DeviceProfile] = None,
        settings: Optional[Settings] = None,
        profile_path: Optional[str] = None,
    ):
        self.profile = profile
        self.settings = settings
        self.profile_path = profile_path

    def _resolve_profile(self) -> DeviceProfile:
        """Resolve profile strictly from passed model or dedicated config file."""
        if self.profile is not None:
            missing = [
                attr
                for attr in self.REQUIRED_ATTRIBUTES
                if not getattr(self.profile, attr, None)
            ]
            if missing:
                try:
                    verified_profile = load_device_profile(self.profile_path, reload=True)
                    for attr in missing:
                        verified_val = getattr(verified_profile, attr, None)
                        if verified_val:
                            setattr(self.profile, attr, verified_val)
                except Exception as exc:
                    raise ConfigurationError(
                        f"DeviceProfile is missing required attribute(s) {missing!r} and verified "
                        f"fallback configuration could not be loaded: {exc}"
                    ) from exc

                still_missing = [
                    attr
                    for attr in self.REQUIRED_ATTRIBUTES
                    if not getattr(self.profile, attr, None)
                ]
                if still_missing:
                    raise ConfigurationError(
                        f"Required attribute(s) {still_missing!r} missing from DeviceProfile "
                        f"and could not be found in verified configuration."
                    )
            return self.profile

        return load_device_profile(self.profile_path)

    def _resolve_settings(self) -> Settings:
        """Resolve settings from passed model or singleton."""
        if self.settings is not None:
            return self.settings
        return get_settings()

    def build_context_envelope(self) -> Dict[str, Any]:
        """Builds and returns the Playwright browser.new_context() envelope dictionary."""
        profile = self._resolve_profile()
        settings = self._resolve_settings()

        envelope: Dict[str, Any] = {
            "viewport": profile.viewport_dict(),
            "user_agent": profile.user_agent,
            "device_scale_factor": profile.device_scale_factor,
            "is_mobile": profile.is_mobile,
            "has_touch": profile.has_touch,
            "locale": profile.locale,
            "timezone_id": profile.timezone_id,
        }

        if profile.permissions:
            envelope["permissions"] = list(profile.permissions)

        geo = profile.geolocation_dict()
        if geo:
            envelope["geolocation"] = geo
            if "geolocation" not in envelope.get("permissions", []):
                envelope.setdefault("permissions", []).append("geolocation")
        elif settings.geolocation_latitude is not None and settings.geolocation_longitude is not None:
            envelope["geolocation"] = {
                "latitude": settings.geolocation_latitude,
                "longitude": settings.geolocation_longitude,
                "accuracy": settings.geolocation_accuracy or 10.0,
            }
            if "geolocation" not in envelope.get("permissions", []):
                envelope.setdefault("permissions", []).append("geolocation")

        if settings.proxy:
            envelope["proxy"] = settings.proxy.to_playwright_dict()

        return envelope
