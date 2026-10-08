"""Inspection summary formatting service."""

from typing import Any, Dict

class InspectionFormatterService:
    """Formats raw inspection schema into a concise, token-optimized summary."""

    @staticmethod
    def format_summary(data: Dict[str, Any]) -> str:
        """Returns a concise, human-readable summary of the inspected form."""
        lines = []
        lines.append(f"=== FORM INSPECTION SUMMARY: '{data.get('title')}' ===")
        lines.append(f"URL: {data.get('url')}\n")

        # Sections
        sections = data.get("sections", [])
        if sections:
            lines.append(f"📁 Sections ({len(sections)}): " + ", ".join(sections))
            lines.append("")

        # Inputs
        inputs = data.get("inputs", [])
        lines.append(f"📝 Text & Numeric Input Fields ({len(inputs)}):")
        for inp in inputs:
            req_flag = " [REQUIRED]" if inp.get("required") else ""
            cur = f" = '{inp['value']}'" if inp.get("value") else ""
            lines.append(f"  • Label: '{inp['label']}' (ID: {inp['id']}){req_flag}{cur}")
        lines.append("")

        # Dropdowns
        dropdowns = data.get("dropdowns", [])
        lines.append(f"🔽 Dropdowns & Picklists ({len(dropdowns)}):")
        for dd in dropdowns:
            req_flag = " [REQUIRED]" if dd.get("required") else ""
            cur = f" = '{dd['value']}'" if dd.get("value") else ""
            opts = dd.get("sample_options") or []
            sample_str = f" [Sample: {', '.join(opts[:4])}]" if opts else ""
            lines.append(f"  • Label: '{dd['label']}' (ID: {dd['id']}){req_flag}{cur}{sample_str}")
        lines.append("")

        # Choices
        choices = data.get("choices", [])
        lines.append(f"🔘 Choice Groups (Radio / Checkbox) ({len(choices)}):")
        for ch in choices:
            req_flag = " [REQUIRED]" if ch.get("required") else ""
            opts_str = ", ".join(ch.get("options", []))
            sel = f" [Selected: {ch['selected']}]" if ch.get("selected") else ""
            lines.append(f"  • Question: '{ch['question']}'{req_flag} -> [{opts_str}]{sel}")
        lines.append("")

        # File Uploads
        uploads = data.get("file_uploads", [])
        lines.append(f"📎 File Upload Areas ({len(uploads)}):")
        for up in uploads:
            req_flag = " [REQUIRED]" if up.get("required") else ""
            lines.append(f"  • Label: '{up['label']}' (ID: {up['id']}){req_flag}")
        if data.get("already_uploaded_files"):
            lines.append(f"    Already attached: {data['already_uploaded_files']}")
        lines.append("")

        # Action Buttons
        buttons = data.get("buttons", [])
        lines.append(f"🔘 Key Action Buttons ({len(buttons)}):")
        for btn in buttons:
            lines.append(f"  • [{btn.get('action', 'action').upper()}] '{btn['text']}' (ID: {btn['id']})")
        lines.append("")

        return "\n".join(lines)
