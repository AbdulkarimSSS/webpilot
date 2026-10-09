import json, sys
d = json.load(sys.stdin)
row = [d.get("scenario"), d.get("tool"), d.get("run"), d.get("mode"),
       d.get("field_accuracy"), d.get("precision"), d.get("recall"),
       d.get("form_pass"), d.get("reported_success"), d.get("false_success"),
       d.get("submitted_count"), json.dumps(d.get("wrong_target") or {}, ensure_ascii=False),
       len(d.get("critical_incidents") or []),
       d.get("steps"), d.get("wall_time_s"), d.get("schema_tokens"),
       d.get("failure_type") or "none"]
print(",".join(str(x) for x in row))
