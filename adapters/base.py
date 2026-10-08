"""Adapter protocols and shared interface contracts."""

from typing import Any, Dict, List, Optional, Protocol
from playwright.sync_api import BrowserContext, Page

class BrowserAdapterProtocol(Protocol):
    """Protocol for browser runtime management."""

    @property
    def page(self) -> Optional[Page]:
        ...

    @property
    def context(self) -> Optional[BrowserContext]:
        ...

    def start(self, cookies_path: Optional[str] = None) -> None:
        ...

    def stop(self) -> None:
        ...

    def navigate(self, url: str, wait_timeout: Optional[int] = None) -> None:
        ...

    def capture_screenshot(self, output_path: str, full_page: bool = False) -> None:
        ...


class UploadAdapterProtocol(Protocol):
    """Protocol for document attachment operations."""

    def upload_document(self, file_path: str, document_type_keyword: str = "") -> bool:
        ...
