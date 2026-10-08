"""Adapters package for universal web applier."""

from adapters.base import BrowserAdapterProtocol, UploadAdapterProtocol
from adapters.browser_adapter import BrowserAdapter
from adapters.upload_adapter import UploadAdapter
import adapters.dom_scripts as dom_scripts

__all__ = [
    "BrowserAdapterProtocol",
    "UploadAdapterProtocol",
    "BrowserAdapter",
    "UploadAdapter",
    "dom_scripts",
]
