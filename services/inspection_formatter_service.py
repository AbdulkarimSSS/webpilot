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
            first_sec = sections[0]
            if isinstance(first_sec, dict) or hasattr(first_sec, "state"):
                lines.append(f"📁 Form Sections & Accordions ({len(sections)}):")
                for sec in sections:
                    s_dict = vars(sec) if hasattr(sec, "__dict__") and not isinstance(sec, dict) else sec
                    lid = f" [{s_dict.get('local_id')}]" if s_dict.get("local_id") else ""
                    name = s_dict.get("title") or s_dict.get("label") or "Section"
                    state = str(s_dict.get("state", "OPEN")).upper()
                    state_badge = f" [{state}]"
                    trigger_parts = []
                    if s_dict.get("trigger_local_id"):
                        trigger_parts.append(f"Toggle: {s_dict['trigger_local_id']}")
                    if s_dict.get("trigger_id"):
                        trigger_parts.append(f"ID: {s_dict['trigger_id']}")
                    toggle_str = f" ({' | '.join(trigger_parts)})" if trigger_parts else ""
                    cnt = s_dict.get("fields_count", 0)
                    if state == "COLLAPSED" and cnt == 0:
                        field_str = " -> 0 visible fields"
                    else:
                        field_str = f" -> {cnt} field{'s' if cnt != 1 else ''}"
                    lines.append(f"  •{lid} '{name}'{state_badge}{toggle_str}{field_str}")
                lines.append("")
            else:
                lines.append(f"📁 Sections ({len(sections)}): " + ", ".join(str(s) for s in sections))
                lines.append("")

        # Inputs
        inputs = data.get("inputs", [])
        lines.append(f"📝 Text & Numeric Input Fields ({len(inputs)}):")
        for inp in inputs:
            req_flag = " [REQUIRED]" if inp.get("required") else ""
            cur = f" = '{inp['value']}'" if inp.get("value") else ""
            lid = f" [{inp['local_id']}]" if inp.get("local_id") else ""
            lines.append(f"  • Label: '{inp['label']}'{lid} (ID: {inp['id']}){req_flag}{cur}")
        lines.append("")

        # Dropdowns
        dropdowns = data.get("dropdowns", [])
        lines.append(f"🔽 Dropdowns & Picklists ({len(dropdowns)}):")
        for dd in dropdowns:
            req_flag = " [REQUIRED]" if dd.get("required") else ""
            cur = f" = '{dd['value']}'" if dd.get("value") else ""
            opts = dd.get("sample_options") or []
            sample_str = f" [Sample: {', '.join(opts[:4])}]" if opts else ""
            lid = f" [{dd['local_id']}]" if dd.get("local_id") else ""
            lines.append(f"  • Label: '{dd['label']}'{lid} (ID: {dd['id']}){req_flag}{cur}{sample_str}")
        lines.append("")

        # Choices
        choices = data.get("choices", [])
        lines.append(f"🔘 Choice Groups (Radio / Checkbox) ({len(choices)}):")
        for ch in choices:
            req_flag = " [REQUIRED]" if ch.get("required") else ""
            opts_str = ", ".join(ch.get("options", []))
            sel = f" [Selected: {ch['selected']}]" if ch.get("selected") else ""
            lid = f" [{ch['local_id']}]" if ch.get("local_id") else ""
            lines.append(f"  • Question: '{ch['question']}'{lid}{req_flag} -> [{opts_str}]{sel}")
        lines.append("")

        # File Uploads
        uploads = data.get("file_uploads", [])
        lines.append(f"📎 File Upload Areas ({len(uploads)}):")
        for up in uploads:
            req_flag = " [REQUIRED]" if up.get("required") else ""
            lid = f" [{up['local_id']}]" if up.get("local_id") else ""
            lines.append(f"  • Label: '{up['label']}'{lid} (ID: {up['id']}){req_flag}")
        if data.get("already_uploaded_files"):
            lines.append(f"    Already attached: {data['already_uploaded_files']}")
        lines.append("")

        # Action Buttons
        buttons = data.get("buttons", [])
        key_buttons = [b for b in buttons if b.get("action") != "toggle_section"]
        lines.append(f"🔘 Key Action Buttons ({len(key_buttons)}):")
        for btn in key_buttons:
            lid = f" [{btn['local_id']}]" if btn.get("local_id") else ""
            b_text = btn.get("text") or btn.get("label") or btn.get("value") or ""
            b_id = btn.get("id") or ""
            lines.append(f"  • [{btn.get('action', 'action').upper()}] '{b_text}'{lid} (ID: {b_id})")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_targeted_summary(data: Dict[str, Any], targets: list[str]) -> str:
        """Formats a concise summary showing ONLY the fields that were targeted during interaction."""
        if not targets:
            return ""

        clean_targets = set()
        for t in targets:
            raw = str(t).strip()
            if raw.startswith("@"):
                clean_targets.add(raw.lower())
            if ":" in raw and not raw.startswith("@"):
                parts = raw.split(":")
                clean_targets.add(parts[-1].strip().lower())
                clean_targets.add(raw.lower())
            else:
                clean_targets.add(raw.lower())

        def matches(item: Dict[str, Any]) -> bool:
            lid = (item.get("local_id") or "").lower()
            iid = (item.get("id") or "").lower()
            lbl = (item.get("label") or item.get("question") or "").lower()
            name = (item.get("name") or "").lower()
            return any(
                ct == lid or ct == iid or ct == name or ct in lbl or lbl in ct
                for ct in clean_targets
            )

        lines = []
        lines.append(f"=== TARGETED FIELDS SUMMARY: '{data.get('title')}' ===")
        lines.append(f"URL: {data.get('url')}\n")

        # Filtered sections
        matched_sections = [
            s for s in data.get("sections", [])
            if (isinstance(s, dict) or hasattr(s, "__dict__")) and matches(vars(s) if hasattr(s, "__dict__") and not isinstance(s, dict) else s)
        ]
        if matched_sections:
            lines.append(f"📁 Form Sections & Accordions ({len(matched_sections)}):")
            for sec in matched_sections:
                s_dict = vars(sec) if hasattr(sec, "__dict__") and not isinstance(sec, dict) else sec
                lid = f" [{s_dict.get('local_id')}]" if s_dict.get("local_id") else ""
                name = s_dict.get("title") or s_dict.get("label") or "Section"
                state = str(s_dict.get("state", "OPEN")).upper()
                state_badge = f" [{state}]"
                trigger_parts = []
                if s_dict.get("trigger_local_id"):
                    trigger_parts.append(f"Toggle: {s_dict['trigger_local_id']}")
                if s_dict.get("trigger_id"):
                    trigger_parts.append(f"ID: {s_dict['trigger_id']}")
                toggle_str = f" ({' | '.join(trigger_parts)})" if trigger_parts else ""
                cnt = s_dict.get("fields_count", 0)
                if state == "COLLAPSED" and cnt == 0:
                    field_str = " -> 0 visible fields"
                else:
                    field_str = f" -> {cnt} field{'s' if cnt != 1 else ''}"
                lines.append(f"  •{lid} '{name}'{state_badge}{toggle_str}{field_str}")
            lines.append("")

        # Filtered inputs
        matched_inputs = [inp for inp in data.get("inputs", []) if matches(inp)]
        if matched_inputs:
            lines.append(f"📝 Text & Numeric Input Fields ({len(matched_inputs)}):")
            for inp in matched_inputs:
                req_flag = " [REQUIRED]" if inp.get("required") else ""
                cur = f" = '{inp['value']}'" if inp.get("value") else ""
                lid = f" [{inp['local_id']}]" if inp.get("local_id") else ""
                lines.append(f"  • Label: '{inp['label']}'{lid} (ID: {inp['id']}){req_flag}{cur}")
            lines.append("")

        # Filtered dropdowns
        matched_dropdowns = [dd for dd in data.get("dropdowns", []) if matches(dd)]
        if matched_dropdowns:
            lines.append(f"🔽 Dropdowns & Picklists ({len(matched_dropdowns)}):")
            for dd in matched_dropdowns:
                req_flag = " [REQUIRED]" if dd.get("required") else ""
                cur = f" = '{dd['value']}'" if dd.get("value") else ""
                lid = f" [{dd['local_id']}]" if dd.get("local_id") else ""
                lines.append(f"  • Label: '{dd['label']}'{lid} (ID: {dd['id']}){req_flag}{cur}")
            lines.append("")

        # Filtered choices
        matched_choices = [ch for ch in data.get("choices", []) if matches(ch)]
        if matched_choices:
            lines.append(f"🔘 Choice Groups ({len(matched_choices)}):")
            for ch in matched_choices:
                req_flag = " [REQUIRED]" if ch.get("required") else ""
                sel = f" [Selected: {ch['selected']}]" if ch.get("selected") else ""
                lid = f" [{ch['local_id']}]" if ch.get("local_id") else ""
                lines.append(f"  • Question: '{ch['question']}'{lid}{req_flag}{sel}")
            lines.append("")

        # Filtered uploads
        matched_uploads = [up for up in data.get("file_uploads", []) if matches(up)]
        if matched_uploads:
            lines.append(f"📎 File Upload Areas ({len(matched_uploads)}):")
            for up in matched_uploads:
                lid = f" [{up['local_id']}]" if up.get("local_id") else ""
                lines.append(f"  • Label: '{up['label']}'{lid} (ID: {up['id']})")
            lines.append("")

        if len(lines) <= 2:
            return ""

        return "\n".join(lines).strip()

