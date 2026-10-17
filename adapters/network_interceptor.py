"""Network Interceptor and Traffic Manager for WebPilot.

Provides:
1. Resource Blocking: Blocking images, stylesheets, fonts, media, and custom URL glob patterns.
2. Network Sniffing: Real-time interception and recording of API/XHR/fetch requests and responses.
3. Asset Dumping: Selective local downloading of site scripts (.js) and JSON endpoints.
4. HAR Recording: Exporting complete network traces (HAR 1.2) for debugging and auditing.
"""

from __future__ import annotations

import datetime
import fnmatch
import json
import os
import re
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Set
from playwright.sync_api import BrowserContext, Page, Request, Response, Route


class NetworkTrafficManager:
    """Manages route blocking, response sniffing, and asset capture across a BrowserContext or Page."""

    IMAGE_EXTENSIONS: Set[str] = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff", ".avif"
    }

    def __init__(self, max_entries: int = 1000):
        self.block_images: bool = False
        self.block_patterns: List[str] = []
        self.sniff_active: bool = False
        self.sniff_types: Set[str] = {"fetch", "xhr"}
        self.sniff_url_pattern: Optional[str] = None
        self.captured_traffic: List[Dict[str, Any]] = []
        self.max_entries: int = max_entries
        self._route_installed: bool = False

    def configure_blocking(
        self,
        block_images: bool = False,
        block_patterns: Optional[List[str]] = None,
    ) -> None:
        """Sets blocking rules for images and URL patterns."""
        self.block_images = block_images
        if block_patterns:
            for p in block_patterns:
                if p and p not in self.block_patterns:
                    self.block_patterns.append(p)

    def should_block_url(self, url: str, resource_type: str) -> bool:
        """Determines if a given URL and resource type should be blocked."""
        # 1. Image blocking
        if self.block_images:
            if resource_type in ("image", "images"):
                return True
            low_url = url.lower().split("?")[0].split("#")[0]
            if any(low_url.endswith(ext) for ext in self.IMAGE_EXTENSIONS):
                return True

        # 2. Pattern matching (glob patterns like *analytics*.js)
        for pattern in self.block_patterns:
            if fnmatch.fnmatch(url, pattern) or fnmatch.fnmatch(url.lower(), pattern.lower()):
                return True
        return False

    def attach_to_context(self, context: BrowserContext) -> None:
        """Installs route handlers and event listeners on a BrowserContext."""
        if not context:
            return

        def handle_route(route: Route) -> None:
            req = route.request
            if self.should_block_url(req.url, req.resource_type):
                try:
                    route.abort()
                    return
                except Exception:
                    pass
            try:
                route.continue_()
            except Exception:
                pass

        try:
            context.route("**/*", handle_route)
            self._route_installed = True
        except Exception:
            pass

        # Response listener for sniffing and caching
        def on_response(response: Response) -> None:
            try:
                req = response.request
                res_type = req.resource_type
                req_url = req.url

                # Filter by sniff types and url pattern when selective sniffing is desired,
                # but also record script/xhr/fetch by default if buffer isn't full.
                matches_type = not self.sniff_types or res_type in self.sniff_types or res_type == "script"
                matches_pattern = True
                if self.sniff_url_pattern:
                    matches_pattern = (
                        fnmatch.fnmatch(req_url, self.sniff_url_pattern)
                        or self.sniff_url_pattern.lower() in req_url.lower()
                    )

                if (self.sniff_active and matches_pattern) or (matches_type and matches_pattern):
                    content_type = response.headers.get("content-type", "")
                    is_json = "json" in content_type or res_type in ("xhr", "fetch")
                    is_script = res_type == "script" or req_url.endswith(".js")
                    body_data: Any = None
                    try:
                        if is_json:
                            body_data = response.json()
                        elif is_script:
                            body_data = response.text()
                        else:
                            text = response.text()
                            if len(text) <= 5000:
                                body_data = text
                            else:
                                body_data = text[:5000] + "... [Truncated]"
                    except Exception:
                        body_data = "[Binary / Unreadable]"

                    entry = {
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "url": req_url,
                        "method": req.method,
                        "resource_type": res_type,
                        "status": response.status,
                        "content_type": content_type,
                        "headers": dict(response.headers),
                        "request_headers": dict(req.headers),
                        "post_data": req.post_data,
                        "body": body_data,
                    }
                    if len(self.captured_traffic) >= self.max_entries:
                        self.captured_traffic.pop(0)
                    self.captured_traffic.append(entry)
            except Exception:
                pass

        try:
            context.on("response", on_response)
        except Exception:
            pass

    def clear_traffic(self) -> None:
        """Clears captured network traffic buffer."""
        self.captured_traffic.clear()

    def dump_assets(
        self,
        output_dir: str,
        types: Optional[List[str]] = None,
        filter_pattern: Optional[str] = None,
        page: Optional[Page] = None,
    ) -> List[str]:
        """Saves captured responses to output_dir grouped by domain and path.

        If page is provided and 'js' is requested, also attempts to pull loaded <script src> elements.
        """
        os.makedirs(output_dir, exist_ok=True)
        saved_files: List[str] = []
        target_types = set(t.lower().strip() for t in (types or ["js", "json"]))

        # First pass: dump from captured traffic
        for i, entry in enumerate(self.captured_traffic):
            url = entry.get("url", "")
            res_type = entry.get("resource_type", "")
            body = entry.get("body")

            if filter_pattern and not (fnmatch.fnmatch(url, filter_pattern) or filter_pattern.lower() in url.lower()):
                continue

            # Determine file extension and matching
            is_js = "js" in target_types and (res_type == "script" or url.endswith(".js"))
            is_json = "json" in target_types and (isinstance(body, (dict, list)) or "json" in entry.get("content_type", ""))

            if not (is_js or is_json):
                continue

            parsed = urllib.parse.urlparse(url)
            base_name = os.path.basename(parsed.path) or f"asset_{i}"
            if is_json and not base_name.endswith(".json"):
                base_name += ".json"
            elif is_js and not base_name.endswith(".js"):
                base_name += ".js"

            safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base_name)
            target_path = os.path.join(output_dir, f"{i:03d}_{safe_name}")

            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    if isinstance(body, (dict, list)):
                        json.dump(body, f, indent=2, ensure_ascii=False)
                    else:
                        f.write(str(body or ""))
                saved_files.append(target_path)
            except Exception:
                continue

        # Second pass: if JS requested and page is available, extract DOM scripts if needed
        if "js" in target_types and page and not page.is_closed():
            try:
                script_urls = page.evaluate("() => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)")
                for idx, s_url in enumerate(script_urls):
                    if not s_url or any(s_url in e.get("url", "") for e in self.captured_traffic):
                        continue
                    parsed = urllib.parse.urlparse(s_url)
                    base_name = os.path.basename(parsed.path) or f"page_script_{idx}.js"
                    if not base_name.endswith(".js"):
                        base_name += ".js"
                    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base_name)
                    target_path = os.path.join(output_dir, f"script_{idx:03d}_{safe_name}")
                    try:
                        resp = page.request.get(s_url)
                        if resp.ok:
                            with open(target_path, "w", encoding="utf-8") as f:
                                f.write(resp.text())
                            saved_files.append(target_path)
                    except Exception:
                        pass
            except Exception:
                pass

        return saved_files

    def export_har(self, output_file: str) -> str:
        """Exports captured traffic into standard HAR 1.2 format JSON."""
        entries = []
        for entry in self.captured_traffic:
            started = entry.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            body = entry.get("body")
            body_str = json.dumps(body) if isinstance(body, (dict, list)) else str(body or "")

            req_headers = [{"name": k, "value": v} for k, v in entry.get("request_headers", {}).items()]
            res_headers = [{"name": k, "value": v} for k, v in entry.get("headers", {}).items()]

            har_entry = {
                "startedDateTime": started,
                "time": 50,
                "request": {
                    "method": entry.get("method", "GET"),
                    "url": entry.get("url", ""),
                    "httpVersion": "HTTP/2.0",
                    "cookies": [],
                    "headers": req_headers,
                    "queryString": [],
                    "headersSize": -1,
                    "bodySize": len(entry.get("post_data") or ""),
                },
                "response": {
                    "status": entry.get("status", 200),
                    "statusText": "OK" if entry.get("status", 200) < 400 else "Error",
                    "httpVersion": "HTTP/2.0",
                    "cookies": [],
                    "headers": res_headers,
                    "content": {
                        "size": len(body_str),
                        "mimeType": entry.get("content_type", "application/json"),
                        "text": body_str,
                    },
                    "redirectURL": "",
                    "headersSize": -1,
                    "bodySize": len(body_str),
                },
                "cache": {},
                "timings": {
                    "send": 5,
                    "wait": 40,
                    "receive": 5,
                },
            }
            if entry.get("post_data"):
                har_entry["request"]["postData"] = {
                    "mimeType": "application/x-www-form-urlencoded",
                    "text": entry.get("post_data"),
                }
            entries.append(har_entry)

        har_doc = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "WebPilot Engine",
                    "version": "2.7.3",
                },
                "pages": [],
                "entries": entries,
            }
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(har_doc, f, indent=2, ensure_ascii=False)

        return os.path.abspath(output_file)


# Global singleton manager per process
_NETWORK_MANAGER: Optional[NetworkTrafficManager] = None


def get_network_manager() -> NetworkTrafficManager:
    """Returns the process-wide NetworkTrafficManager singleton."""
    global _NETWORK_MANAGER
    if _NETWORK_MANAGER is None:
        _NETWORK_MANAGER = NetworkTrafficManager()
    return _NETWORK_MANAGER
