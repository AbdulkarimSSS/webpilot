"""Precision HTML Diagnostics Pipeline for WebPilot (find --html).

Implements a 5-stage linear pipeline:
[1. Target & Ascent] -> [2. Search & Spine Pruning] -> [3. Structural Filter] -> [4. Pretty-Print] -> [5. Final Slicing & Guard]
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString, Comment


class DiagnosticSearchNotFoundError(Exception):
    """Raised when --search target query is not found within the root boundary subtree."""
    pass


class HTMLDiagnosticService:
    """Multi-stage surgical HTML filtering and formatting pipeline."""

    _pruned_registry: Dict[str, Dict[str, Any]] = {}
    _exc_counter: int = 0
    PRUNED_STORE_DIR: str = os.path.expanduser("~/.webpilot")
    PRUNED_STORE_FILE: str = os.path.join(PRUNED_STORE_DIR, "pruned_nodes.json")

    @classmethod
    def clear_pruned_store(cls) -> None:
        """Clears both in-memory registry and disk cache for pruned nodes."""
        cls._pruned_registry.clear()
        cls._exc_counter = 0
        if os.path.exists(cls.PRUNED_STORE_FILE):
            try:
                os.remove(cls.PRUNED_STORE_FILE)
            except Exception:
                pass

    @classmethod
    def _save_pruned_store(cls) -> None:
        """Persists in-memory pruned registry to disk."""
        try:
            os.makedirs(cls.PRUNED_STORE_DIR, exist_ok=True)
            with open(cls.PRUNED_STORE_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._pruned_registry, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @classmethod
    def _load_pruned_store(cls) -> None:
        """Loads pruned registry from disk cache if file exists."""
        if os.path.exists(cls.PRUNED_STORE_FILE):
            try:
                with open(cls.PRUNED_STORE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cls._pruned_registry.update(data)
            except Exception:
                pass

    @classmethod
    def _compute_depth(cls, tag: Tag) -> int:
        """Calculates the maximum tree depth of descendants inside tag."""
        max_depth = 0
        for desc in tag.find_all():
            d = 0
            curr = desc
            while curr != tag and curr is not None:
                d += 1
                curr = curr.parent
            if d > max_depth:
                max_depth = d
        return max_depth

    @classmethod
    def register_pruned_node(
        cls,
        node: Tag,
        include_tags: Optional[str] = None,
    ) -> str:
        """Analyzes a pruned node, registers it with an @exc-N ID, and returns the ID."""
        cls._exc_counter += 1
        exc_id = f"@exc-{cls._exc_counter}"

        tag_name = node.name.lower() if node.name else "unknown"
        dom_id = node.get("id")
        raw_classes = node.get("class", [])
        classes = (
            [c.lower() for c in raw_classes]
            if isinstance(raw_classes, list)
            else [str(raw_classes).lower()]
        ) if raw_classes else []

        raw_html = str(node)
        chars = len(raw_html)
        lines = len(raw_html.splitlines())
        depth = cls._compute_depth(node)

        element_counts: Dict[str, int] = {}
        field_types: Dict[str, int] = {}

        for el in node.find_all():
            t_name = el.name.lower()
            element_counts[t_name] = element_counts.get(t_name, 0) + 1
            if t_name == "input":
                inp_type = el.get("type", "text").lower()
                field_types[inp_type] = field_types.get(inp_type, 0) + 1

        matching_include = 0
        if include_tags:
            inc_set = {t.strip().lower() for t in include_tags.split(",") if t.strip()}
            matching_include = sum(element_counts.get(t, 0) for t in inc_set)

        selector_parts = [tag_name]
        if classes:
            selector_parts.append("." + ".".join(classes[:3]))
        if dom_id:
            selector_parts.append(f"#{dom_id}")
        selector_desc = "".join(selector_parts)

        meta = {
            "exc_id": exc_id,
            "tag": tag_name,
            "dom_id": dom_id,
            "classes": classes,
            "selector_desc": selector_desc,
            "raw_html": raw_html,
            "chars": chars,
            "lines": lines,
            "depth": depth,
            "element_counts": element_counts,
            "field_types": field_types,
            "matching_include": matching_include,
        }

        cls._pruned_registry[exc_id] = meta
        cls._save_pruned_store()
        return exc_id

    @classmethod
    def get_pruned_node(cls, exc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves pruned node metadata by @exc-N identifier."""
        if exc_id in cls._pruned_registry:
            return cls._pruned_registry[exc_id]
        cls._load_pruned_store()
        return cls._pruned_registry.get(exc_id)

    @classmethod
    def format_pruned_info(cls, meta: Dict[str, Any]) -> str:
        """Formats pruned node metadata into a concise, token-saving diagnostic block."""
        exc_id = meta.get("exc_id", "@exc")
        selector_desc = meta.get("selector_desc", "element")
        chars = meta.get("chars", 0)
        lines = meta.get("lines", 0)
        depth = meta.get("depth", 0)
        element_counts = meta.get("element_counts", {})
        field_types = meta.get("field_types", {})
        matching_include = meta.get("matching_include", 0)

        out = [f"{exc_id}  ({selector_desc})"]
        out.append(f"  chars: {chars:,}   lines: {lines}   depth: {depth} levels")

        if matching_include > 0:
            out.append(f"  include matches: {matching_include}")

        if element_counts:
            out.append("  inner elements:")
            priority_order = ["input", "select", "textarea", "button", "label", "table", "div", "span"]
            sorted_tags = sorted(
                element_counts.keys(),
                key=lambda t: (priority_order.index(t) if t in priority_order else 99, -element_counts[t])
            )
            for t in sorted_tags[:10]:
                cnt = element_counts[t]
                extra = ""
                if t == "input" and field_types:
                    types_str = ", ".join(f"{k}: {v}" for k, v in list(field_types.items())[:4])
                    extra = f"   (types: {types_str})"
                out.append(f"    • {t:<8} x{cnt}{extra}")

        return "\n".join(out)

    FIELD_CONTAINER_CLASSES: Set[str] = {
        "form-group",
        "rcmformfield",
        "rcmformsection",
        "form-field",
        "form-item",
        "form-row",
        "field",
        "field-wrapper",
        "input-group",
        "control-group",
        "form-group-item",
        "radio-group",
        "radiogroup",
    }

    FIELD_CONTAINER_TAGS: Set[str] = {
        "tr",
        "fieldset",
        "details",
        "li",
    }

    STUBBED_TAGS: Dict[str, str] = {
        "svg": "[SVG ICON]",
        "script": "[SCRIPT]",
        "style": "[STYLE]",
        "noscript": "[NOSCRIPT]",
    }

    COMPOSITE_INNER_TAGS: Set[str] = {
        "path",
        "circle",
        "rect",
        "line",
        "polyline",
        "polygon",
        "g",
        "defs",
        "use",
        "text",
        "tspan",
        "ellipse",
        "clippath",
        "mask",
        "option",
        "optgroup",
    }

    @classmethod
    def _is_match(cls, node: Tag, query_pattern: re.Pattern | str, is_regex: bool) -> bool:
        """Evaluates whether a DOM node's text or attributes match the search query."""
        if not isinstance(node, Tag):
            return False

        # 1. Attribute matching (id, name, aria-label, placeholder, class, data-*, title, value)
        for attr_key, attr_val in node.attrs.items():
            val_str = " ".join(attr_val) if isinstance(attr_val, list) else str(attr_val)
            if is_regex:
                if query_pattern.search(val_str) or (attr_key.startswith("data-") and query_pattern.search(attr_key)):
                    return True
            else:
                if query_pattern in val_str.lower() or (attr_key.startswith("data-") and query_pattern in attr_key.lower()):
                    return True

        # 2. Direct / leaf text matching
        direct_text = "".join(c for c in node.children if isinstance(c, NavigableString)).strip()
        full_text = node.get_text().strip()
        text_to_check = direct_text if direct_text else full_text

        if is_regex:
            return bool(query_pattern.search(text_to_check))
        return query_pattern in text_to_check.lower()

    @classmethod
    def _find_matching_leaf(cls, root: Tag, search_query: str) -> Optional[Tag]:
        """Finds the most specific leaf element matching the search query within root."""
        clean_query = search_query.strip()
        is_regex = clean_query.startswith(("re:", "regex:"))
        if is_regex:
            raw_pat = clean_query.split(":", 1)[1].strip()
            pattern = re.compile(raw_pat, re.IGNORECASE)
        else:
            pattern = clean_query.lower()

        matched_elements: List[Tag] = []
        for el in root.find_all():
            if cls._is_match(el, pattern, is_regex):
                matched_elements.append(el)

        if not matched_elements:
            # Check root itself
            if cls._is_match(root, pattern, is_regex):
                return root
            return None

        # Sort by depth / fewest descendants to target the deepest, most specific element
        matched_elements.sort(key=lambda e: len(e.find_all()))
        return matched_elements[0]

    @classmethod
    def _identify_field_container(cls, matched_node: Tag, root_boundary: Tag) -> Tag:
        """Finds the immediate enclosing field container (e.g. .form-group, tr, fieldset)."""
        curr = matched_node
        while curr and curr != root_boundary:
            # Check class names
            class_val = curr.get("class", [])
            class_str = " ".join(class_val).lower() if isinstance(class_val, list) else str(class_val).lower()
            if any(fc in class_str for fc in cls.FIELD_CONTAINER_CLASSES):
                return curr

            # Check tag names
            if curr.name.lower() in cls.FIELD_CONTAINER_TAGS:
                return curr

            curr = curr.parent

        # Fallback: parent container (or matched node itself if already top-level)
        if matched_node.parent and matched_node.parent != root_boundary:
            p = matched_node.parent
            if p.name.lower() in ("label", "span", "strong", "b", "em") and p.parent and p.parent != root_boundary:
                return p.parent
            return p
        return matched_node

    @classmethod
    def _matches_upper_token(cls, node: Tag, token: str) -> bool:
        """Determines if an upper-tier uncle element matches an upper-include token."""
        if not isinstance(node, Tag):
            return False
        clean_token = token.strip().lower()
        if not clean_token:
            return False

        # 1. Direct tag name match (e.g. 'header', 'h2', 'button')
        if node.name.lower() == clean_token:
            return True

        # 2. Class match (e.g. '.section-toolbar' or 'section-toolbar')
        class_target = clean_token[1:] if clean_token.startswith(".") else clean_token
        node_classes = (
            [c.lower() for c in node.get("class", [])]
            if isinstance(node.get("class"), list)
            else [str(node.get("class", "")).lower()]
        )
        if class_target in node_classes:
            return True

        # 3. ID match (e.g. '#header-id')
        if clean_token.startswith("#"):
            id_target = clean_token[1:]
            if node.get("id", "").lower() == id_target:
                return True

        # 4. Check if node contains a matching descendant
        if node.find(clean_token):
            return True
        try:
            if node.select_one(clean_token):
                return True
        except Exception:
            pass

        return False

    @classmethod
    def _apply_upper_exclude(cls, container: Tag, tokens: List[str]) -> None:
        """Purges unwanted child elements from inside spared upper-tier elements."""
        for token in tokens:
            clean_tok = token.strip().lower()
            if not clean_tok:
                continue

            for el in list(container.find_all(clean_tok)):
                if el.parent is None:
                    continue
                stub = cls.STUBBED_TAGS.get(clean_tok)
                if stub:
                    el.clear()
                    el.string = stub
                else:
                    el.decompose()

            if clean_tok.startswith("."):
                target_cls = clean_tok[1:]
                for el in list(container.find_all()):
                    if el.parent is None:
                        continue
                    classes = (
                        [c.lower() for c in el.get("class", [])]
                        if isinstance(el.get("class"), list)
                        else [str(el.get("class", "")).lower()]
                    )
                    if target_cls in classes:
                        el.decompose()

    @classmethod
    def prune_ancestral_spine(
        cls,
        root: Tag,
        matched_node: Tag,
        upper_include: Optional[str] = None,
        upper_exclude: Optional[str] = None,
        include_tags: Optional[str] = None,
    ) -> Tuple[Tag, Tag]:
        """
        Prunes all sibling branches outside the ancestral spine down to the field container,
        sparing upper uncle branches matching upper_include, and purging child elements matching upper_exclude
        from inside spared upper-tier elements. Pruned elements are indexed with @exc-N identifiers.
        Returns: (root, field_container)
        """
        if matched_node == root:
            return root, root

        field_container = cls._identify_field_container(matched_node, root)

        upper_inc_tokens: Optional[List[str]] = (
            [t.strip() for t in upper_include.split(",") if t.strip()]
            if upper_include
            else None
        )
        upper_exc_tokens: Optional[List[str]] = (
            [t.strip() for t in upper_exclude.split(",") if t.strip()]
            if upper_exclude
            else None
        )

        # From field_container up to root, prune irrelevant siblings unless spared by upper_include
        curr = field_container
        while curr and curr != root:
            parent = curr.parent
            if not parent:
                break
            for child in list(parent.children):
                if child != curr:
                    if isinstance(child, NavigableString):
                        child.extract()
                        continue
                    if not isinstance(child, Tag):
                        continue

                    spared = False
                    if upper_inc_tokens:
                        spared = any(cls._matches_upper_token(child, tok) for tok in upper_inc_tokens)

                    if spared:
                        if upper_exc_tokens:
                            cls._apply_upper_exclude(child, upper_exc_tokens)
                    else:
                        exc_id = cls.register_pruned_node(child, include_tags=include_tags)
                        meta = cls._pruned_registry[exc_id]
                        comment_text = f" [PRUNED: {exc_id} ({meta['tag']}) | {meta['chars']:,} chars | {meta['lines']} lines] "
                        child.replace_with(Comment(comment_text))

            curr = parent

        return root, field_container

    @classmethod
    def apply_structural_tag_filter(
        cls,
        root: Tag,
        include_tags: Optional[str] = None,
        exclude_tags: Optional[str] = None,
    ) -> Tag:
        """
        Applies Stage 3 include/exclude structural tag filters.
        Precedence: Exclude takes priority over Include upon conflict (Exclude > Include).
        Result = (Include elements) - (Exclude elements).
        """
        inc_set: Optional[Set[str]] = (
            {t.strip().lower() for t in include_tags.split(",") if t.strip()}
            if include_tags
            else None
        )
        exc_set: Optional[Set[str]] = (
            {t.strip().lower() for t in exclude_tags.split(",") if t.strip()}
            if exclude_tags
            else None
        )

        # 1. Effective include whitelist is stripped of any explicitly excluded tags
        effective_inc: Optional[Set[str]] = None
        if inc_set is not None:
            effective_inc = inc_set - exc_set if exc_set else inc_set

        # 2. Exclude pass (strips or stubs tags matching exc_set)
        if exc_set:
            for tag_name in exc_set:
                for el in list(root.find_all(tag_name)):
                    if el.parent is None:
                        continue
                    stub = cls.STUBBED_TAGS.get(tag_name)
                    if stub:
                        el.clear()
                        el.string = stub
                    else:
                        el.decompose()

        # 3. Include pass (whitelist) using effective_inc
        if effective_inc is not None:
            for el in list(root.find_all()):
                if el.parent is None or el == root:
                    continue
                tag_lower = el.name.lower()
                # If this tag was already handled as a stubbed tag in exclude pass, preserve the stub
                if exc_set and tag_lower in exc_set and tag_lower in cls.STUBBED_TAGS:
                    continue
                if tag_lower not in effective_inc:
                    # If this is a child of a composite tag (e.g. circle in svg, option in select) and the parent is included
                    if tag_lower in cls.COMPOSITE_INNER_TAGS and any(
                        p.name and p.name.lower() in effective_inc for p in el.parents
                    ):
                        continue
                    # Check if this element holds any descendants that ARE included
                    has_included_child = any(
                        ch.name and ch.name.lower() in effective_inc for ch in el.find_all()
                    )
                    if has_included_child:
                        # Unwrap non-included container to retain nested included elements
                        el.unwrap()
                    else:
                        el.decompose()

        return root

    @classmethod
    def format_html(cls, root: Tag, pretty: bool = True) -> str:
        """Formats DOM tree into indented lines or returns raw representation."""
        if not pretty:
            return str(root)

        # Standard clean pretty formatting
        formatted = root.prettify()
        # Clean excessive empty lines
        lines = [line for line in formatted.splitlines() if line.strip()]
        return "\n".join(lines)

    @classmethod
    def _collect_lines_backwards(
        cls,
        lines: List[str],
        target_line: int,
        max_chars: Optional[int],
        show_all: bool,
    ) -> Tuple[List[str], int, int, bool]:
        """
        Anchors at target_line (1-indexed) and collects preceding lines backwards
        until reaching line 1 or the max_chars ceiling.
        Returns: (selected_lines, start_line_num, end_line_num, truncated_start)
        """
        total_lines = len(lines)
        if total_lines == 0 or target_line <= 0:
            return [], 0, 0, False

        end_line_num = min(target_line, total_lines)

        # If show_all or unconstrained, return from line 1 to end_line_num
        if show_all or max_chars is None or max_chars <= 0:
            return lines[:end_line_num], 1, end_line_num, False

        # Check if lines from line 1 to end_line_num fit within max_chars
        full_candidate = lines[:end_line_num]
        full_len = sum(len(l) for l in full_candidate) + max(0, len(full_candidate) - 1)
        if full_len <= max_chars:
            return full_candidate, 1, end_line_num, False

        # Collect backwards from end_line_num - 1
        collected: List[str] = []
        curr_chars = 0
        start_idx = end_line_num - 1

        for i in range(end_line_num - 1, -1, -1):
            line_len = len(lines[i])
            needed = line_len + (1 if collected else 0)
            if curr_chars + needed > max_chars:
                if not collected:
                    collected.append(lines[i])
                    start_idx = i
                break
            collected.append(lines[i])
            curr_chars += needed
            start_idx = i

        collected.reverse()
        start_line_num = start_idx + 1
        truncated_start = (start_line_num > 1)
        return collected, start_line_num, end_line_num, truncated_start

    @classmethod
    def _stream_lines_forward_clamped(
        cls,
        candidate_lines: List[str],
        max_chars: Optional[int],
        show_all: bool,
    ) -> str:
        """
        Streams lines forward until max_chars ceiling is reached,
        truncating and appending a warning notice if ceiling is exceeded.
        """
        full_text = "\n".join(candidate_lines)
        total_chars = len(full_text)
        if show_all or max_chars is None or max_chars <= 0 or total_chars <= max_chars:
            return full_text

        streamed: List[str] = []
        curr_chars = 0
        for line in candidate_lines:
            needed = len(line) + (1 if streamed else 0)
            if curr_chars + needed > max_chars:
                if not streamed:
                    streamed.append(line[:max_chars])
                    curr_chars = max_chars
                break
            streamed.append(line)
            curr_chars += needed

        streamed_text = "\n".join(streamed)
        actual_chars = len(streamed_text)
        notice = f"\n... [Truncated: showing first {actual_chars:,} of {total_chars:,} characters. Use --all or --max-chars <N> to view more]"
        return f"{streamed_text}{notice}"

    @classmethod
    def apply_line_slice_with_banner(
        cls,
        text: str,
        slice_str: Optional[str],
        max_chars: Optional[int] = 20000,
        show_all: bool = False,
    ) -> Tuple[str, Optional[str]]:
        """
        Applies 1-indexed Python slice notation to line-formatted output,
        returning a tuple of (content_body, optional_banner).
        This guarantees the banner is completely isolated and never clipped by subsequent --chars.
        """
        if not slice_str or not slice_str.strip():
            return text, None

        s = slice_str.strip()
        lines = text.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return text, None

        # Variant 2 (bare integer <X>) or negative tail integer (-<X>)
        if ":" not in s:
            try:
                val = int(s)
                if val < 0:
                    # Variant 5 equivalent without colon: tail lines (-<X>)
                    tail_val = abs(val)
                    candidate = lines[-tail_val:] if total_lines > tail_val else lines
                    return cls._stream_lines_forward_clamped(candidate, max_chars, show_all), None
                else:
                    # Variant 2: Head as bare integer <X> -> Target-anchored backwards window
                    collected, start_line, end_line, truncated = cls._collect_lines_backwards(
                        lines, target_line=val, max_chars=max_chars, show_all=show_all
                    )
                    content = "\n".join(collected)
                    banner = None
                    if truncated:
                        banner = f"[Note: Displaying target-anchored window preceding line {val} (lines {start_line} to {end_line}). Use --all to view from line 1]"
                    return content, banner
            except ValueError:
                return text, None

        parts = s.split(":", 1)
        start_str, end_str = parts[0].strip(), parts[1].strip()

        # Variant 3: Head slice notation (:<X>)
        if not start_str and end_str:
            try:
                val = int(end_str)
                if val <= 0:
                    target_line = max(1, total_lines + val)
                else:
                    target_line = val

                collected, start_line, end_line, truncated = cls._collect_lines_backwards(
                    lines, target_line=target_line, max_chars=max_chars, show_all=show_all
                )
                content = "\n".join(collected)
                banner = None
                if truncated:
                    banner = f"[Note: Displaying target-anchored window preceding line {target_line} (lines {start_line} to {end_line}). Use --all to view from line 1]"
                return content, banner
            except ValueError:
                return text, None

        # Variant 4 (<X>:) or Variant 5 (-<X>:)
        if start_str and not end_str:
            try:
                start_val = int(start_str)
                if start_val < 0:
                    # Variant 5: Tail slice (-<X>:) -> CLAMPED BY DEFAULT CEILING (20,000)
                    tail_val = abs(start_val)
                    candidate = lines[-tail_val:] if total_lines > tail_val else lines
                    return cls._stream_lines_forward_clamped(candidate, max_chars, show_all), None
                else:
                    # Variant 4: Offset to end (<X>:) -> CLAMPED BY DEFAULT CEILING (20,000)
                    start_idx = max(0, start_val - 1) if start_val > 0 else 0
                    candidate = lines[start_idx:]
                    return cls._stream_lines_forward_clamped(candidate, max_chars, show_all), None
            except ValueError:
                return text, None

        # Variant 1: Explicit Range (<start>:<end>) -> UNCONSTRAINED
        try:
            start_val = int(start_str)
            end_val = int(end_str)
            start_idx = max(0, start_val - 1) if start_val > 0 else max(total_lines + start_val, 0)
            end_idx = min(total_lines, end_val) if end_val >= 0 else max(total_lines + end_val, 0)
            return "\n".join(lines[start_idx:end_idx]), None
        except ValueError:
            return text, None

    @classmethod
    def apply_line_slice(
        cls,
        text: str,
        slice_str: Optional[str],
        max_chars: Optional[int] = 20000,
        show_all: bool = False,
    ) -> str:
        """
        Applies 1-indexed Python slice notation to line-formatted output
        implementing all 5 Stage 5 variants and differential ceiling rules.
        """
        content, banner = cls.apply_line_slice_with_banner(text, slice_str, max_chars, show_all)
        if banner:
            return f"{banner}\n{content}"
        return content

    @classmethod
    def apply_char_slice(
        cls,
        text: str,
        slice_str: Optional[str],
        max_chars: Optional[int] = 20000,
        show_all: bool = False,
    ) -> str:
        """
        Applies 0-indexed slice notation to character stream
        implementing all 5 Stage 5 variants and differential ceiling rules.
        """
        if not slice_str or not slice_str.strip():
            return text

        s = slice_str.strip()

        # Variant 2 (bare integer <X>) or negative tail integer (-<X>)
        if ":" not in s:
            try:
                val = int(s)
                if val < 0:
                    # Variant 5 equivalent without colon: tail chars -> UNCONSTRAINED
                    tail = abs(val)
                    return text[-tail:]
                else:
                    # Variant 2: Head as bare integer <X> -> UNCONSTRAINED [0, X]
                    return text[:val]
            except ValueError:
                return text

        parts = s.split(":", 1)
        start_str, end_str = parts[0].strip(), parts[1].strip()

        # Variant 3: Head slice notation (:<X>) -> UNCONSTRAINED [0, X]
        if not start_str and end_str:
            try:
                val = int(end_str)
                return text[:val]
            except ValueError:
                return text

        # Variant 4 (<X>:) or Variant 5 (-<X>:)
        if start_str and not end_str:
            try:
                start_val = int(start_str)
                if start_val < 0:
                    # Variant 5: Tail slice (-<X>:) -> UNCONSTRAINED (exactly the last X chars)
                    tail = abs(start_val)
                    return text[-tail:]
                else:
                    # Variant 4: Offset to end (<X>:) -> CLAMPED BY DEFAULT CEILING (20,000)
                    raw_slice = text[start_val:]
                    slice_total = len(raw_slice)
                    if not show_all and max_chars is not None and max_chars > 0 and slice_total > max_chars:
                        truncated = raw_slice[:max_chars]
                        return f"{truncated}\n... [Truncated: showing first {max_chars:,} of {slice_total:,} characters. Use --all or --max-chars <N> to view more]"
                    return raw_slice
            except ValueError:
                return text

        # Variant 1: Explicit Range (<start>:<end>) -> UNCONSTRAINED
        try:
            start_val = int(start_str)
            end_val = int(end_str)
            return text[start_val:end_val]
        except ValueError:
            return text

    @classmethod
    def apply_safety_guard(
        cls,
        text: str,
        max_chars: Optional[int] = 20000,
        show_all: bool = False,
    ) -> str:
        """Enforces character ceiling truncation guard unless explicitly bypassed with --all."""
        if show_all or max_chars is None or max_chars <= 0:
            return text

        total_len = len(text)
        if total_len > max_chars:
            truncated = text[:max_chars]
            return f"{truncated}\n... [Truncated: showing first {max_chars:,} of {total_len:,} characters. Use --all or --max-chars <N> to view more]"
        return text

    @classmethod
    def process_html_pipeline(
        cls,
        raw_html: str,
        search_query: Optional[str] = None,
        include_tags: Optional[str] = None,
        exclude_tags: Optional[str] = None,
        upper_include: Optional[str] = None,
        upper_exclude: Optional[str] = None,
        pretty: bool = True,
        lines_slice: Optional[str] = None,
        chars_slice: Optional[str] = None,
        max_chars: Optional[int] = 20000,
        show_all: bool = False,
    ) -> str:
        """Executes the full 5-stage HTML diagnostics pipeline."""
        if not raw_html or not raw_html.strip():
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")
        root = soup.find()
        if not root or not isinstance(root, Tag):
            return raw_html

        field_container: Optional[Tag] = None
        # Stage 2: Semantic Search & Ancestral Spine Pruning
        if search_query and search_query.strip():
            matched_node = cls._find_matching_leaf(root, search_query)
            if not matched_node:
                raise DiagnosticSearchNotFoundError(
                    f"Search target '{search_query}' not found within element boundary"
                )
            root, field_container = cls.prune_ancestral_spine(
                root,
                matched_node,
                upper_include=upper_include,
                upper_exclude=upper_exclude,
                include_tags=include_tags,
            )

        # Stage 3: Structural Tag Filtering (exclude > include)
        # Lower-tier filter applies strictly to field_container (if search was performed)
        if include_tags or exclude_tags:
            target_filter_root = field_container if field_container is not None else root
            cls.apply_structural_tag_filter(target_filter_root, include_tags, exclude_tags)

        # Stage 4: DOM Formatting & Indentation
        formatted = cls.format_html(root, pretty=pretty)

        # Stage 5: Final Slicing & Safety Guard (Sequential Pipeline: [Apply --lines slice] -> [Apply --chars slice])
        banner: Optional[str] = None
        if lines_slice:
            formatted, banner = cls.apply_line_slice_with_banner(
                formatted, lines_slice, max_chars=max_chars, show_all=show_all
            )

        if chars_slice:
            # The character offsets in --chars are relative to the block of lines extracted by --lines
            formatted = cls.apply_char_slice(
                formatted, chars_slice, max_chars=max_chars, show_all=show_all
            )

        if banner:
            formatted = f"{banner}\n{formatted}"

        if not lines_slice and not chars_slice:
            formatted = cls.apply_safety_guard(
                formatted, max_chars=max_chars, show_all=show_all
            )

        return formatted
