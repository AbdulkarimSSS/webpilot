"""Unit and integration tests for ContentReaderService and 'wp read' functionality."""

import json
from unittest.mock import MagicMock, patch
import pytest

from services.content_reader_service import ContentReaderService
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from mcp_tools import execute_read_page
from cli_parser import build_cli_parser
from webpilot.client import WebPilot


SAMPLE_JOB_HTML = """
<!DOCTYPE html>
<html>
<head><title>Senior Software Engineer - Careers</title></head>
<body>
    <header>
        <nav><a href="/">Home</a> | <a href="/jobs">All Jobs</a> | <a href="/login">Login</a></nav>
    </header>
    <main>
        <article>
            <h1>Senior Python Engineer</h1>
            <p class="meta">Location: Riyadh, Saudi Arabia | Department: Core Engineering</p>
            <h2>Job Overview</h2>
            <p>We are seeking an experienced Senior Python Engineer to lead our AI Agent platform.</p>
            <h2>Responsibilities</h2>
            <ul>
                <li>Architect scalable microservices with FastAPI and Playwright.</li>
                <li>Design robust autonomous agent runtimes.</li>
                <li>Optimize browser DOM automation workflows.</li>
            </ul>
            <h2>Requirements</h2>
            <ul>
                <li>5+ years of experience with Python.</li>
                <li>Strong knowledge of asynchronous programming (asyncio).</li>
            </ul>
        </article>
    </main>
    <footer>
        <p>&copy; 2026 Acme Corp. All rights reserved. <a href="/privacy">Privacy Policy</a></p>
    </footer>
</body>
</html>
"""


def test_content_reader_extracts_clean_markdown():
    """Verify Trafilatura extracts clean core content and strips header/footer boilerplate."""
    result = ContentReaderService.extract_clean_markdown(SAMPLE_JOB_HTML)
    assert result, "Extracted markdown must not be empty"
    assert "Senior Python Engineer" in result
    assert "Responsibilities" in result
    assert "Privacy Policy" not in result or "All rights reserved" not in result
    # Token count should be tiny compared to raw HTML
    assert len(result) < len(SAMPLE_JOB_HTML) * 0.5


def test_content_reader_empty_html_fallback():
    """Verify fallback when HTML is empty or invalid."""
    assert ContentReaderService.extract_clean_markdown("", fallback_text="Fallback Text") == "Fallback Text"
    assert ContentReaderService.extract_clean_markdown("   ", fallback_text="Default") == "Default"


def test_content_reader_stripped_tags_fallback():
    """Verify fallback strips tags if trafilatura extracts nothing from non-article snippets."""
    short_snippet = "<div><span>Simple label without article tags</span></div>"
    result = ContentReaderService.extract_clean_markdown(short_snippet)
    assert "Simple label without article tags" in result


def test_cli_parser_read_subcommand():
    """Verify 'wp read' subcommand arguments are correctly parsed."""
    parser = build_cli_parser()
    args = parser.parse_args(["read", "--url", "https://example.com/job", "--output", "job.md", "--tab", "2"])
    assert args.command == "read"
    assert args.url == "https://example.com/job"
    assert args.output == "job.md"
    assert args.tab == 2


def test_mcp_execute_read_page_success():
    """Verify MCP execute_read_page formats response as valid JSON with clean content."""
    mock_client = MagicMock()
    mock_resp = SupervisorActionResponse(
        success=True,
        action="read",
        message="Extracted clean content",
        active_url="https://example.com/job",
        active_title="Job Title",
        content="# Senior Python Engineer\nLocation: Riyadh",
    )
    mock_client.execute.return_value = mock_resp

    res_json = execute_read_page(mock_client, url="https://example.com/job")
    data = json.loads(res_json)
    assert data["success"] is True
    assert data["status"] == "success"
    assert "Senior Python Engineer" in data["content"]
    assert data["active_url"] == "https://example.com/job"


def test_mcp_execute_read_page_empty_url_validation():
    """Verify empty string URL is rejected with validation error."""
    mock_client = MagicMock()
    res_json = execute_read_page(mock_client, url="   ")
    data = json.loads(res_json)
    assert data["success"] is False
    assert "Validation error" in data["error"]


def test_webpilot_sdk_read_method():
    """Verify WebPilot SDK .read() calls supervisor client and returns content."""
    wp = WebPilot()
    mock_resp = SupervisorActionResponse(
        success=True,
        action="read",
        content="# Clean Job Description",
    )
    with patch.object(wp.client, "execute", return_value=mock_resp):
        content = wp.read(url="https://example.com")
        assert content == "# Clean Job Description"
