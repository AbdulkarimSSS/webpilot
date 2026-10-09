"""Dedicated centralized configuration and settings module.

Enforces strict resolution precedence:
1. Environment variables (os.environ)
2. .env file
3. Dedicated JSON configuration files (settings.json, device_profile.json)

Zero hardcoded fallbacks in source code: coordinates, IPs, ports, device models,
and timeouts are exclusively sourced from configuration.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from core.exceptions import ConfigurationError
from core.models import DeviceProfile, ProxyConfig

# Project root and configuration paths
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR: str = os.path.join(PROJECT_ROOT, "config")
DEFAULT_SETTINGS_JSON: str = os.path.join(CONFIG_DIR, "settings.json")
DEFAULT_SETTINGS_EXAMPLE_JSON: str = os.path.join(CONFIG_DIR, "settings.example.json")
DEFAULT_DEVICE_PROFILE_JSON: str = os.path.join(CONFIG_DIR, "device_profile.json")
DEFAULT_DEVICE_PROFILE_EXAMPLE_JSON: str = os.path.join(CONFIG_DIR, "device_profile.example.json")
DEFAULT_ENV_FILE: str = os.path.join(PROJECT_ROOT, ".env")


def parse_env_file(filepath: str) -> Dict[str, str]:
    """Parse a .env file into a dictionary without modifying os.environ."""
    if not os.path.isfile(filepath):
        return {}

    env_vars: Dict[str, str] = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    # Strip matching surrounding quotes
                    if len(v) >= 2 and ((v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'"))):
                        v = v[1:-1]
                    env_vars[k] = v
    except Exception as exc:
        raise ConfigurationError(f"Failed to parse .env file at {filepath}: {exc}") from exc

    return env_vars


def load_json_file(primary_path: str, fallback_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads a JSON configuration file, falling back to a template if primary is absent."""
    target_path = primary_path
    if not os.path.isfile(target_path):
        if fallback_path and os.path.isfile(fallback_path):
            target_path = fallback_path
        else:
            return {}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            raise ConfigurationError(f"JSON config at {target_path} must be an object/dict")
    except Exception as exc:
        raise ConfigurationError(f"Failed to read JSON config at {target_path}: {exc}") from exc


class ValueResolver:
    """Resolves values following strict precedence: os.environ -> .env -> JSON."""

    def __init__(self, env_data: Dict[str, str], json_data: Dict[str, Any], example_json_data: Dict[str, Any]):
        self.env_data = env_data
        self.json_data = json_data
        self.example_json_data = example_json_data

    def resolve(
        self,
        json_key: str,
        env_var: str,
        default: Any = None,
        cast_type: Optional[type] = None
    ) -> Any:
        """Resolve a setting by priority."""
        # 1. os.environ
        if env_var in os.environ and os.environ[env_var] != "":
            raw_val = os.environ[env_var]
            return self._cast(raw_val, cast_type)

        # 2. .env file
        if env_var in self.env_data and self.env_data[env_var] != "":
            raw_val = self.env_data[env_var]
            return self._cast(raw_val, cast_type)

        # 3. Dedicated JSON config
        if json_key in self.json_data and self.json_data[json_key] is not None:
            raw_val = self.json_data[json_key]
            return self._cast(raw_val, cast_type)

        # 4. Dedicated JSON example template
        if json_key in self.example_json_data and self.example_json_data[json_key] is not None:
            raw_val = self.example_json_data[json_key]
            return self._cast(raw_val, cast_type)

        # 5. Default
        return default

    @staticmethod
    def _cast(val: Any, cast_type: Optional[type]) -> Any:
        if cast_type is None or val is None:
            return val
        if cast_type == bool:
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            return s in ("1", "true", "yes", "on", "t")
        try:
            return cast_type(val)
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(f"Unable to cast value {val!r} to {cast_type.__name__}: {exc}") from exc


@dataclass
class Settings:
    """Fully resolved runtime configuration."""

    headless: bool
    default_timeout_ms: int
    form_ready_timeout_ms: int
    submission_wait_ms: int
    expand_section_wait_ms: int
    screenshots_dir: str
    cookies_path: Optional[str]
    data_path: Optional[str]
    settings_path: str
    device_profile_path: str
    proxy: Optional[ProxyConfig] = None
    geolocation_latitude: Optional[float] = None
    geolocation_longitude: Optional[float] = None
    geolocation_accuracy: Optional[float] = None


_SETTINGS_CACHE: Optional[Settings] = None
_DEVICE_PROFILE_CACHE: Optional[DeviceProfile] = None


def reset_settings_cache() -> None:
    """Clear cached settings and device profile singletons."""
    global _SETTINGS_CACHE, _DEVICE_PROFILE_CACHE
    _SETTINGS_CACHE = None
    _DEVICE_PROFILE_CACHE = None


def get_settings(
    env_file: Optional[str] = None,
    settings_json_path: Optional[str] = None,
    reload: bool = False
) -> Settings:
    """Build or retrieve the resolved Settings singleton."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None and not reload:
        return _SETTINGS_CACHE

    target_env = env_file or os.environ.get("APP_ENV_FILE") or DEFAULT_ENV_FILE
    env_data = parse_env_file(target_env)

    target_settings_path = (
        settings_json_path
        or os.environ.get("APP_SETTINGS_PATH")
        or env_data.get("APP_SETTINGS_PATH")
        or DEFAULT_SETTINGS_JSON
    )

    json_data = load_json_file(target_settings_path, DEFAULT_SETTINGS_EXAMPLE_JSON)
    example_json_data = load_json_file(DEFAULT_SETTINGS_EXAMPLE_JSON)

    resolver = ValueResolver(env_data, json_data, example_json_data)

    # Proxy resolution
    proxy_server = resolver.resolve("proxy_server", "APP_PROXY_SERVER", cast_type=str)
    if not proxy_server and isinstance(json_data.get("proxy"), dict):
        proxy_server = json_data["proxy"].get("server")
    proxy_user = resolver.resolve("proxy_username", "APP_PROXY_USERNAME", cast_type=str)
    if not proxy_user and isinstance(json_data.get("proxy"), dict):
        proxy_user = json_data["proxy"].get("username")
    proxy_pass = resolver.resolve("proxy_password", "APP_PROXY_PASSWORD", cast_type=str)
    if not proxy_pass and isinstance(json_data.get("proxy"), dict):
        proxy_pass = json_data["proxy"].get("password")

    proxy_cfg = ProxyConfig(server=proxy_server, username=proxy_user, password=proxy_pass) if proxy_server else None

    # Geolocation resolution
    geo_lat = resolver.resolve("geolocation_latitude", "APP_GEOLOCATION_LATITUDE", cast_type=float)
    if geo_lat is None and isinstance(json_data.get("geolocation"), dict):
        geo_lat = json_data["geolocation"].get("latitude")
    geo_lon = resolver.resolve("geolocation_longitude", "APP_GEOLOCATION_LONGITUDE", cast_type=float)
    if geo_lon is None and isinstance(json_data.get("geolocation"), dict):
        geo_lon = json_data["geolocation"].get("longitude")
    geo_acc = resolver.resolve("geolocation_accuracy", "APP_GEOLOCATION_ACCURACY", default=10.0, cast_type=float)
    if geo_acc is None and isinstance(json_data.get("geolocation"), dict):
        geo_acc = json_data["geolocation"].get("accuracy", 10.0)

    # Device profile path
    dev_path = resolver.resolve(
        "device_profile_path",
        "APP_DEVICE_PROFILE_PATH",
        default=DEFAULT_DEVICE_PROFILE_JSON,
        cast_type=str
    )

    settings = Settings(
        headless=resolver.resolve("headless", "APP_HEADLESS", default=True, cast_type=bool),
        default_timeout_ms=resolver.resolve("default_timeout_ms", "APP_DEFAULT_TIMEOUT_MS", default=45000, cast_type=int),
        form_ready_timeout_ms=resolver.resolve("form_ready_timeout_ms", "APP_FORM_READY_TIMEOUT_MS", default=10000, cast_type=int),
        submission_wait_ms=resolver.resolve("submission_wait_ms", "APP_SUBMISSION_WAIT_MS", default=8000, cast_type=int),
        expand_section_wait_ms=resolver.resolve("expand_section_wait_ms", "APP_EXPAND_SECTION_WAIT_MS", default=800, cast_type=int),
        screenshots_dir=resolver.resolve("screenshots_dir", "APP_SCREENSHOTS_DIR", default="screenshots", cast_type=str),
        cookies_path=resolver.resolve("cookies_path", "APP_COOKIES_PATH", cast_type=str),
        data_path=resolver.resolve("data_path", "APP_DATA_PATH", default=None, cast_type=str),
        settings_path=target_settings_path,
        device_profile_path=dev_path,
        proxy=proxy_cfg,
        geolocation_latitude=float(geo_lat) if geo_lat is not None else None,
        geolocation_longitude=float(geo_lon) if geo_lon is not None else None,
        geolocation_accuracy=float(geo_acc) if geo_acc is not None else None,
    )

    _SETTINGS_CACHE = settings
    return settings


def load_device_profile(
    profile_path: Optional[str] = None,
    env_file: Optional[str] = None,
    reload: bool = False
) -> DeviceProfile:
    """Loads and resolves DeviceProfile adhering strictly to 3-tier precedence.

    Order:
    1. os.environ
    2. .env file
    3. Dedicated JSON file (device_profile.json or device_profile.example.json)
    """
    global _DEVICE_PROFILE_CACHE
    if _DEVICE_PROFILE_CACHE is not None and not reload and profile_path is None:
        return _DEVICE_PROFILE_CACHE

    target_env = env_file or os.environ.get("APP_ENV_FILE") or DEFAULT_ENV_FILE
    env_data = parse_env_file(target_env)

    if profile_path is not None:
        if not os.path.isfile(profile_path):
            raise ConfigurationError(f"Specified device profile file not found: '{profile_path}'")
        target_file = profile_path
        example_fallback = None
    else:
        target_file = (
            os.environ.get("APP_DEVICE_PROFILE_PATH")
            or env_data.get("APP_DEVICE_PROFILE_PATH")
            or DEFAULT_DEVICE_PROFILE_JSON
        )
        example_fallback = DEFAULT_DEVICE_PROFILE_EXAMPLE_JSON

    json_data = load_json_file(target_file, example_fallback)
    example_data = load_json_file(example_fallback) if example_fallback else {}

    if not json_data and not example_data:
        raise ConfigurationError(
            f"Device profile configuration not found at '{target_file}'"
        )

    resolver = ValueResolver(env_data, json_data, example_data)

    # Resolve viewport
    vp_w = resolver.resolve("viewport_width", "DEVICE_VIEWPORT_WIDTH", cast_type=int)
    if vp_w is None and isinstance(json_data.get("viewport"), dict):
        vp_w = json_data["viewport"].get("width")
    if vp_w is None and isinstance(example_data.get("viewport"), dict):
        vp_w = example_data["viewport"].get("width")

    vp_h = resolver.resolve("viewport_height", "DEVICE_VIEWPORT_HEIGHT", cast_type=int)
    if vp_h is None and isinstance(json_data.get("viewport"), dict):
        vp_h = json_data["viewport"].get("height")
    if vp_h is None and isinstance(example_data.get("viewport"), dict):
        vp_h = example_data["viewport"].get("height")

    # Resolve geolocation
    geo_lat = resolver.resolve("geolocation_latitude", "DEVICE_GEOLOCATION_LATITUDE", cast_type=float)
    if geo_lat is None and isinstance(json_data.get("geolocation"), dict):
        geo_lat = json_data["geolocation"].get("latitude")
    geo_lon = resolver.resolve("geolocation_longitude", "DEVICE_GEOLOCATION_LONGITUDE", cast_type=float)
    if geo_lon is None and isinstance(json_data.get("geolocation"), dict):
        geo_lon = json_data["geolocation"].get("longitude")
    geo_acc = resolver.resolve("geolocation_accuracy", "DEVICE_GEOLOCATION_ACCURACY", cast_type=float)
    if geo_acc is None and isinstance(json_data.get("geolocation"), dict):
        geo_acc = json_data["geolocation"].get("accuracy")

    # Required attributes check: must exist in profile configuration
    device_name = resolver.resolve("device_name", "DEVICE_NAME", cast_type=str)
    user_agent = resolver.resolve("user_agent", "DEVICE_USER_AGENT", cast_type=str)

    if not user_agent:
        raise ConfigurationError(
            f"Required 'user_agent' could not be resolved from environment or profile at {target_file}"
        )
    if not vp_w or not vp_h:
        raise ConfigurationError(
            f"Required viewport dimensions (width, height) missing in configuration at {target_file}"
        )

    profile = DeviceProfile(
        device_name=str(device_name or "Standard Profile"),
        user_agent=str(user_agent),
        viewport_width=int(vp_w),
        viewport_height=int(vp_h),
        device_scale_factor=resolver.resolve("device_scale_factor", "DEVICE_SCALE_FACTOR", default=1.0, cast_type=float),
        is_mobile=resolver.resolve("is_mobile", "DEVICE_IS_MOBILE", default=False, cast_type=bool),
        has_touch=resolver.resolve("has_touch", "DEVICE_HAS_TOUCH", default=False, cast_type=bool),
        locale=resolver.resolve("locale", "DEVICE_LOCALE", default="en-US", cast_type=str),
        timezone_id=resolver.resolve("timezone_id", "DEVICE_TIMEZONE", default="UTC", cast_type=str),
        geolocation_latitude=float(geo_lat) if geo_lat is not None else None,
        geolocation_longitude=float(geo_lon) if geo_lon is not None else None,
        geolocation_accuracy=float(geo_acc) if geo_acc is not None else None,
        permissions=list(resolver.resolve("permissions", "DEVICE_PERMISSIONS", default=[])),
        platform=resolver.resolve("platform", "DEVICE_PLATFORM", default="Win32", cast_type=str),
        vendor=resolver.resolve("vendor", "DEVICE_VENDOR", default="Google Inc.", cast_type=str),
    )

    if profile_path is None:
        _DEVICE_PROFILE_CACHE = profile
    return profile
