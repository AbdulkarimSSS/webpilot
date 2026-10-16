"""High-density clean content extraction service powered by Trafilatura."""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class ContentReaderService:
    """Extracts ultra-dense, clean Markdown content from HTML and live DOM."""

    @staticmethod
    def extract_clean_markdown(
        html: str,
        include_tables: bool = True,
        include_links: bool = True,
        include_images: bool = False,
        fallback_text: Optional[str] = None,
    ) -> str:
        """Extracts clean markdown from an HTML string using Trafilatura.

        If Trafilatura extraction produces empty output (e.g. extremely short DOM or pure JS shell),
        falls back gracefully to fallback_text or stripped HTML text.
        """
        if not html or not html.strip():
            return fallback_text or ""

        try:
            import trafilatura

            extracted = trafilatura.extract(
                html,
                output_format="markdown",
                include_tables=include_tables,
                include_links=include_links,
                include_images=include_images,
                favor_precision=True,
            )
            if extracted and extracted.strip():
                return extracted.strip()
        except ImportError:
            logger.warning("Trafilatura is not installed; falling back to raw text extraction.")
        except Exception as exc:
            logger.warning(f"Trafilatura extraction notice: {exc}")

        # Fallback if trafilatura extracted nothing or is missing
        if fallback_text and fallback_text.strip():
            return fallback_text.strip()

        # Whitespace and tag cleanup fallback
        clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
