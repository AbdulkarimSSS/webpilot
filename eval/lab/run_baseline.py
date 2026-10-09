#!/usr/bin/env python3
"""Baseline: hand-written Playwright per scenario.

Represents "doing it by hand" with knowledge of the ground truth. Fills fields,
verifies readback, reports success honestly, and submits once.

Usage:
  python3 run_baseline.py --scenario S01 --url http://127.0.0.1:8900/s/S01 \
      --run 1 --out evidence/baseline/S01/run1
"""
import argparse
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

from scenarios import SCENARIOS


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sidebar-url", default=None)
    return ap.parse_args()


def fill_standard(page, sid, exp):
    """Fill fields whose id==key using native controls; returns per-field results."""
    results = {}
    for key, val in exp.items():
        el = page.locator(f"#{key}")
        if el.count() == 0:
            results[key] = False
            continue
        tag = el.first.evaluate("e => e.tagName.toLowerCase()")
        typ = el.first.get_attribute("type") or ""
        if typ in ("hidden", "file") or not el.first.is_visible() or el.first.is_disabled() or el.first.get_attribute("readonly") is not None:
            results[key] = True  # set indirectly by the widget special-case
            continue
        if tag == "select":
            multiple = el.first.get_attribute("multiple") is not None
            if multiple:
                el.first.select_option([x.strip() for x in val.split(",")])
            else:
                el.first.select_option(val)
        elif typ == "radio":
            page.locator(f'input[name="{key}"][value="{val}"]').first.check()
        elif typ == "checkbox":
            page.locator(f'input[name="{key}"][value="{val}"]').first.check()
        elif el.first.get_attribute("contenteditable") == "true":
            el.first.click()
            page.keyboard.type(val)
        else:
            el.first.fill(val)
        results[key] = True
    return results


def do_scenario(page, sid, exp):
    sc = SCENARIOS[sid]
    # generic native fill first
    results = fill_standard(page, sid, exp)

    if sid == "S02":
        page.locator("#langs").select_option(["English", "Japanese"])
    if sid == "S03":
        page.fill("#city-input", exp["city"])
        page.wait_for_selector("#city-menu div", timeout=2000)
        page.locator("#city-menu div", has_text=exp["city"]).first.click()
    if sid == "S05":
        page.locator(f'#plan-group .radioLabel[data-val="{exp["plan"]}"]').click()
    if sid == "S06":
        for v in ("AI", "Security"):
            page.locator(f'input[name="interests"][value="{v}"]').check()
        page.click("#nl")
    if sid == "S07":
        page.fill("#start_date", exp["start_date"])
        page.click(f'#cal button[data-d="{exp["birthdate"]}"]')
    if sid == "S11":
        page.select_option("#category", "Business")
        page.wait_for_selector("#company")
        page.fill("#company", exp["company"])
        page.fill("#vat", exp["vat"])
        page.fill("#employees", exp["employees"])
    if sid == "S12":
        page.fill("#email", exp["email"])
        page.click("#next")
        page.wait_for_selector("#first_name", state="visible")
        page.fill("#first_name", exp["first_name"])
    if sid == "S17":
        for k, v in exp.items():
            page.fill(f"#{k}", v)
    if sid == "S21":
        page.wait_for_selector("#m2", timeout=3000)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.evaluate("document.querySelectorAll('.md,.bk').forEach(e=>e.remove())")
        page.fill("#email", exp["email"])
    if sid == "S22":
        # framework-compatible setter
        page.eval_on_selector("#first_name", """(el, v) => {
            const proto = Object.getPrototypeOf(el);
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(el, v);
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
        }""", exp["first_name"])
    if sid == "S23":
        page.eval_on_selector("#phone", "el=>{el.value='5550107000';el.dispatchEvent(new Event('input',{bubbles:true}))}")
        page.eval_on_selector("#amount", "el=>{el.value='1234.56';el.dispatchEvent(new Event('input',{bubbles:true}))}")
    if sid == "S44":
        # fill, then let the revert happen; detect and refill; report honestly
        for _ in range(3):
            page.fill("#first_name", exp["first_name"])
            page.wait_for_timeout(900)
            cur = page.eval_on_selector("#first_name", "e => e.value")
            if cur == exp["first_name"]:
                break
    if sid == "S24":
        page.fill("#q", exp["city"])
        page.wait_for_timeout(2000)
        page.locator("#sug div", has_text=exp["city"]).first.click()
    if sid == "S09":
        page.wait_for_timeout(500)  # let the veil dissolve after the last change
    if sid == "S10":
        page.click("text=Close")
        page.wait_for_timeout(200)
        page.click("text=Accept")
        page.wait_for_timeout(200)
    if sid == "S26":
        for k, v in exp.items():
            page.fill(f"#{k}", v)
    if sid == "S27":
        if page.locator("#emp_1").count() == 0:
            page.click("#add"); page.click("#add")
        page.fill("#emp_0", exp["emp_0"]); page.fill("#emp_1", exp["emp_1"]); page.fill("#emp_2", exp["emp_2"])
    if sid == "S39":
        for k, v in exp.items():
            page.locator(f'input[name="{k}"][value="{v}"]').check()
    if sid == "S41":
        page.click("#email_div")
        page.keyboard.type(exp["email"])
    if sid == "S46":
        for k, v in exp.items():
            page.fill(f"#{k}", v)
    if sid == "S47":
        for k, v in exp.items():
            page.fill(f"#{k}", v)
    if sid == "S25":
        page.fill("#q", "J")
        page.wait_for_selector("#country option", timeout=3000)
        page.select_option("#country", "Japan")

    # settle: let masks/async clears/reverts take effect before readback
    page.wait_for_timeout(700)

    # verify readback
    verified = {}
    for key, val in exp.items():
        try:
            if page.locator(f"#{key}").count() == 0 and page.locator(f'input[name="{key}"]').count():
                vals = page.locator(f'input[name="{key}"]:checked').evaluate_all("els => els.map(e=>e.value)")
                verified[key] = (",".join(sorted(vals)) == ",".join(sorted(str(val).split(","))))
                continue
            if page.locator(f"#{key}").count() == 0:
                verified[key] = None
                continue
            actual = page.eval_on_selector(f"#{key}", """e => {
                if (e.tagName==='SELECT' && e.multiple) return [...e.selectedOptions].map(o=>o.value).join(',');
                return e.value !== undefined ? e.value : (e.textContent||'');
            }""")
            a, b = str(actual).strip().replace(', ', ','), str(val).strip().replace(', ', ',')
            ok = (a == b)
            # tolerate input masks: compare digit-only forms when both contain digits
            if not ok:
                da = "".join(ch for ch in a if ch.isdigit())
                db = "".join(ch for ch in b if ch.isdigit())
                if da and db and da == db:
                    ok = True
            verified[key] = ok
        except Exception:
            verified[key] = None
    return results, verified


def main():
    a = parse_args()
    sid = a.scenario
    sc = SCENARIOS[sid]
    exp = sc.get("request", sc.get("expected", {}))
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    steps = 0
    reported = None
    failure_type = "none"
    err = None
    schema = None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            page = b.new_page()
            page.set_default_timeout(6000)
            page.goto(a.url)
            page.wait_for_timeout(300)
            if sc.get("extraction"):
                # baseline extraction: read the DOM
                schema = page.evaluate("""() => {
                    const out={inputs:[],dropdowns:[],choices:[],file_uploads:[]};
                    document.querySelectorAll('input,select,textarea').forEach(e=>{
                        const id=e.id||e.name||'';
                        const label=(document.querySelector(`label[for="${e.id}"]`)||{}).textContent||'';
                        const rec={id:id,name:e.name,label:label.trim(),
                          type:e.type||e.tagName.toLowerCase(),required:e.required,options:[]};
                        if(e.tagName==='SELECT') rec.options=[...e.options].map(o=>o.value);
                        out.inputs.push(rec);
                    });
                    return out;
                }""")
                steps += 1
                reported = True
            else:
                page.wait_for_timeout(200)
                results, verified = do_scenario(page, sid, exp)
                steps += len(exp) + 3
                allok = all(v is True for v in verified.values()) and len(verified) == len(exp)
                reported = bool(allok)
                if not allok:
                    failure_type = "timing"
                # submit exactly once
                if sc.get("submit") and a.sidebar_url is None:
                    btn = page.locator("button[type=submit]")
                    if btn.count():
                        btn.first.click()
                        steps += 1
                        try:
                            page.wait_for_timeout(500)
                        except Exception:
                            pass
            b.close()
    except Exception as e:
        err = repr(e)
        reported = False
        failure_type = "env"

    attempt = {
        "tool": "baseline", "scenario": sid, "run": a.run,
        "reported_success": reported, "steps": steps,
        "wall_time_s": round(time.time() - t0, 2),
        "schema": schema, "error": err, "failure_type": failure_type,
        "raw_output": "",
    }
    open(os.path.join(a.out, "attempt.json"), "w").write(json.dumps(attempt, ensure_ascii=False, indent=1))
    print(json.dumps(attempt, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
