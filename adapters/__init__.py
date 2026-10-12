"""Adapters package for universal web applier."""

from adapters.base import BrowserAdapterProtocol, UploadAdapterProtocol
from adapters.browser_adapter import BrowserAdapter
from adapters.locator_fallbacks import PlaywrightLocatorFallback
from adapters.upload_adapter import UploadAdapter
import adapters.dom_scripts as dom_scripts

__all__ = [
    "BrowserAdapterProtocol",
    "UploadAdapterProtocol",
    "BrowserAdapter",
    "PlaywrightLocatorFallback",
    "UploadAdapter",
    "dom_scripts",
]
