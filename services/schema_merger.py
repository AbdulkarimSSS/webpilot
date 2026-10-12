"""Schema merging and LocalID delta reconciliation service."""

from __future__ import annotations

from typing import Any, Dict


class SchemaMerger:
    """Performs smart delta merging of inspected page schemas, preserving stable LocalIDs."""

    CATEGORIES = ("inputs", "dropdowns", "choices", "file_uploads", "buttons")

    @classmethod
    def merge(cls, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Merges two schemas from the same URL, preserving LocalIDs and existing fields."""
        merged = dict(new_schema)
        for cat in cls.CATEGORIES:
            old_items = old_schema.get(cat, [])
            new_items = new_schema.get(cat, [])
            existing_by_id = {item.get("id"): item for item in old_items if item.get("id")}
            combined = []
            seen_ids = set()

            for n in new_items:
                nid = n.get("id")
                if nid and nid in existing_by_id:
                    if existing_by_id[nid].get("local_id") and not n.get("local_id"):
                        n["local_id"] = existing_by_id[nid]["local_id"]
                combined.append(n)
                if nid:
                    seen_ids.add(nid)

            for o in old_items:
                oid = o.get("id")
                if oid and oid not in seen_ids:
                    combined.append(o)
                    seen_ids.add(oid)

            merged[cat] = combined

        return merged
