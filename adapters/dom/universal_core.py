"""Universal DOM core utilities for recursive Shadow DOM piercing and field classification.

Provides zero-hardcoding discovery, multi-tier unwrapping, and cross-framework event synthesis
for any standard or custom web element across modern SPAs (React, Vue, Angular, Lit, Stencil,
Web Components, SAP UI5, Workday, Salesforce LWC, Oracle JET, and raw HTML/Div-soup).
"""

from typing import Final

UNIVERSAL_DOM_CORE_JS: Final[str] = r"""
// --- Universal DOM Core Helpers ---

function cleanStr(t, mode) {
    if (!t) return '';
    let res = String(t);
    if (mode === 'strip') {
        res = res.replace(/[\uE000-\uF8FF]/g, '');
    } else if (mode === 'escape') {
        res = res.replace(/[\uE000-\uF8FF]/g, ch => '\\u' + ch.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0'));
    }
    return res.replace(/[\u00a0\r\n\t]+/g, ' ')
              .replace(/^[\s\*]+/, '')
              .trim();
}

// 1. Recursive Open Shadow DOM Piercing
function deepQueryAll(root, selector) {
    const results = [];
    const visited = new Set();
    function walk(node) {
        if (!node || visited.has(node)) return;
        visited.add(node);
        try {
            if (node.querySelectorAll) {
                const matched = node.querySelectorAll(selector);
                for (let i = 0; i < matched.length; i++) results.push(matched[i]);
            }
        } catch(e) {}
        try {
            const allNodes = node.querySelectorAll ? node.querySelectorAll('*') : [];
            for (let i = 0; i < allNodes.length; i++) {
                const sub = allNodes[i];
                if (sub && sub.shadowRoot) {
                    walk(sub.shadowRoot);
                }
            }
        } catch(e) {}
    }
    walk(root || document);
    return results;
}

function deepGetElementById(root, id) {
    if (!id) return null;
    const direct = document.getElementById(id);
    if (direct) return direct;
    const all = deepQueryAll(root || document, '[id]');
    for (let i = 0; i < all.length; i++) {
        if (all[i].id === id) return all[i];
    }
    return null;
}

// 2. Arbitrary Selector Resolution (CSS, XPath, Piercing Shadow DOM, Colon-ID Safe)
function deepQuerySelector(root, selector) {
    if (!selector || typeof selector !== 'string') return null;
    const trimmed = selector.trim();
    if (!trimmed) return null;

    const baseRoot = root || document;

    // 2a. XPath expression evaluation
    if (trimmed.startsWith('//') || trimmed.startsWith('xpath=') || trimmed.startsWith('xpath:')) {
        let xpath = trimmed;
        if (xpath.startsWith('xpath=')) xpath = xpath.substring(6);
        else if (xpath.startsWith('xpath:')) xpath = xpath.substring(6);
        try {
            const doc = (baseRoot && baseRoot.nodeType === 9) ? baseRoot : ((baseRoot && baseRoot.ownerDocument) || document);
            const contextNode = (baseRoot && baseRoot.nodeType === 9) ? doc.documentElement : baseRoot;
            const xRes = doc.evaluate(xpath, contextNode, null, 9 /* FIRST_ORDERED_NODE_TYPE */, null);
            if (xRes && xRes.singleNodeValue) return xRes.singleNodeValue;
        } catch(e) {}
    }

    // 2b. Normalize CSS selector prefix
    let css = trimmed;
    if (css.startsWith('css=') || css.startsWith('css:')) css = css.substring(4).trim();
    else if (css.startsWith('selector=') || css.startsWith('selector:')) css = css.substring(9).trim();

    // 2c. Direct recursive open Shadow DOM search
    try {
        const deepRes = deepQueryAll(baseRoot, css);
        if (deepRes.length > 0) return deepRes[0];
    } catch(e) {}

    // 2d. Handle ID selectors with unescaped colons (e.g. div#250:_datepicker or #250:_datepicker)
    if (css.includes('#') && css.includes(':')) {
        const fixedCss = css.replace(/#([a-zA-Z0-9_\-\.:]+)/g, (m, idVal) => '[id="' + idVal + '"]');
        try {
            const byFixed = deepQueryAll(baseRoot, fixedCss);
            if (byFixed.length > 0) return byFixed[0];
        } catch(e) {}
    }

    // 2e. Standard querySelector fallback
    try {
        if (baseRoot.querySelector) {
            const stdRes = baseRoot.querySelector(css);
            if (stdRes) return stdRes;
        }
    } catch(e) {}

    return null;
}

// 2. Universal Custom Element & Shadow Input Resolution (Zero hardcoded tag lists)
function isCustomElement(el) {
    if (!el || !el.tagName) return false;
    const tag = el.tagName.toLowerCase();
    if (tag.includes('-')) return true;
    if (el.shadowRoot) return true;
    if (el.getAttribute && el.getAttribute('is')) return true;
    if (window.customElements && typeof window.customElements.get === 'function' && window.customElements.get(tag)) return true;
    return false;
}

function resolveWebComponent(el) {
    if (!el) return null;
    if (isCustomElement(el)) return el;
    if (el.children) {
        for (let i = 0; i < el.children.length; i++) {
            if (isCustomElement(el.children[i])) return el.children[i];
        }
    }
    if (el.querySelectorAll) {
        try {
            const allSubs = el.querySelectorAll('*');
            for (let i = 0; i < allSubs.length; i++) {
                if (isCustomElement(allSubs[i])) return allSubs[i];
            }
        } catch(e) {}
    }
    return null;
}

function resolveShadowInput(el) {
    const wc = resolveWebComponent(el) || el;
    if (!wc) return null;
    try {
        if (wc.shadowRoot) {
            const direct = wc.shadowRoot.querySelector('input:not([type="hidden"]), textarea, [contenteditable="true"], [role="textbox"], [role="combobox"]');
            if (direct) return direct;
            const nested = deepQueryAll(wc.shadowRoot, 'input:not([type="hidden"]), textarea, [contenteditable="true"], [role="textbox"], [role="combobox"]');
            if (nested.length > 0) return nested[0];
        }
    } catch(e) {}
    return null;
}

// 3. Universal Honeypot & Hidden Element Detection
function isHoneypotOrHidden(el) {
    if (!el) return true;
    if (el.offsetParent === null) {
        const tag = (el.tagName || '').toLowerCase();
        if (['select', 'input', 'button'].includes(tag)) {
            const p = el.parentElement;
            if (p && p.offsetParent !== null && (p.offsetWidth > 10 || p.offsetHeight > 10)) {
                return false;
            }
        }
        return true;
    }
    try {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') return true;
        if (parseFloat(style.opacity) === 0 && !['radio', 'checkbox', 'file'].includes(el.type)) return true;
    } catch(e) {}
    if (el.getAttribute('aria-hidden') === 'true') return true;
    const name = (el.name || el.id || '').toLowerCase();
    if (el.getAttribute('tabindex') === '-1' && (name.includes('hp_') || name.includes('honeypot'))) return true;
    try {
        const rect = el.getBoundingClientRect();
        if (rect.right < 0 || rect.bottom < 0 || rect.left < -500 || rect.top < -500) return true;
        if (rect.width === 0 && rect.height === 0 && !['radio', 'checkbox'].includes(el.type)) return true;
    } catch(e) {}
    return false;
}

// 4. Universal Label Resolution
function getUniversalLabel(el, sanitizePua) {
    if (!el) return '';
    const clean = s => cleanStr(s, sanitizePua ? 'strip' : 'escape');
    
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
    if (el.getAttribute('accessible-name')) return clean(el.getAttribute('accessible-name'));
    if (el.getAttribute('title')) return clean(el.getAttribute('title'));
    
    const lblBy = el.getAttribute('aria-labelledby');
    if (lblBy) {
        const root = el.getRootNode ? el.getRootNode() : document;
        const ids = lblBy.split(/\s+/);
        const parts = [];
        for (const id of ids) {
            const refEl = (root.getElementById ? root.getElementById(id) : null) || document.getElementById(id);
            if (refEl && refEl.innerText) parts.push(refEl.innerText);
        }
        if (parts.length > 0) return clean(parts.join(' '));
    }
    
    if (el.id) {
        const root = el.getRootNode ? el.getRootNode() : document;
        const lbl = (root.querySelector ? root.querySelector('label[for="' + el.id + '"]') : null) || document.querySelector('label[for="' + el.id + '"]');
        if (lbl && lbl.innerText) return clean(lbl.innerText);
    }
    
    const wc = resolveWebComponent(el);
    if (wc && wc !== el) {
        const wcLbl = wc.getAttribute('accessible-name') || wc.getAttribute('aria-label') || wc.getAttribute('title') || wc.getAttribute('label');
        if (wcLbl) return clean(wcLbl);
    }
    
    const parentLbl = el.closest ? el.closest('label') : null;
    if (parentLbl && parentLbl.innerText) return clean(parentLbl.innerText);
    
    if (el.previousElementSibling) {
        const prev = el.previousElementSibling;
        const prevText = clean(prev.innerText || prev.textContent);
        if (prevText && prevText.length < 60 && !['input', 'select', 'textarea', 'button'].includes((prev.tagName || '').toLowerCase())) {
            return prevText;
        }
    }
    
    const container = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, .row, fieldset, div') : null;
    if (container) {
        const lblEl = container.querySelector('label, .control-label, .field-label, th, dt, span.label, strong, legend');
        if (lblEl && lblEl !== el && lblEl.innerText) {
            return clean(lblEl.innerText);
        }
        const text = clean(container.innerText || '');
        const firstLine = text.split('\n')[0].trim();
        if (firstLine && firstLine.length < 60) return clean(firstLine);
    }
    
    return clean(el.placeholder || (wc && wc.getAttribute('placeholder')) || el.name || '');
}

// 5. Universal Date Normalization
function normalizeUniversalDate(toSet, formatPattern) {
    if (!toSet || typeof toSet !== 'string') return { value: toSet, isValid: true };
    const str = toSet.trim();
    if (!str) return { value: '', isValid: true };
    
    const iso = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    const slash = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    
    let year = 0, month = 0, day = 0;
    if (iso) {
        year = parseInt(iso[1], 10);
        month = parseInt(iso[2], 10);
        day = parseInt(iso[3], 10);
    } else if (slash) {
        const isMDY = (formatPattern || '').toLowerCase().startsWith('mm');
        if (isMDY) {
            month = parseInt(slash[1], 10);
            day = parseInt(slash[2], 10);
        } else {
            day = parseInt(slash[1], 10);
            month = parseInt(slash[2], 10);
        }
        year = parseInt(slash[3], 10);
    }
    
    if (year === 0 && month === 0 && day === 0) {
        return { value: toSet, isValid: true };
    }
    
    const dt = new Date(year, month - 1, day);
    const isValid = (
        month >= 1 && month <= 12 &&
        day >= 1 && day <= 31 &&
        year >= 1900 && year <= 2100 &&
        dt.getFullYear() === year &&
        dt.getMonth() === month - 1 &&
        dt.getDate() === day
    );
    
    const pat = (formatPattern || 'dd/MM/yyyy').toLowerCase();
    let formatted = str;
    if (pat.includes('yyyy') && pat.includes('mm') && pat.includes('dd')) {
        const dd = String(day).padStart(2, '0');
        const mm = String(month).padStart(2, '0');
        const yyyy = String(year);
        if (pat.startsWith('yyyy-mm-dd') || pat.includes('yyyy-mm-dd')) {
            formatted = `${yyyy}-${mm}-${dd}`;
        } else if (pat.startsWith('mm/dd')) {
            formatted = `${mm}/${dd}/${yyyy}`;
        } else if (pat.includes('.')) {
            formatted = `${dd}.${mm}.${yyyy}`;
        } else if (pat.includes('-')) {
            formatted = `${dd}-${mm}-${yyyy}`;
        } else {
            formatted = `${dd}/${mm}/${yyyy}`;
        }
    }
    
    return { value: formatted, isValid };
}

// 8. Direct Detection of Linked / Dependent Parent Field (Cascading Picklists / Conditional Inputs)
function detectDependentParentField(el) {
    if (!el) return null;
    const isDisabled = Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled'));
    const isSelect = (el.tagName || '').toLowerCase() === 'select';
    
    // Check explicit HTML5 / framework cascading linkage attributes
    const explicitParent = el.getAttribute('data-parent') || 
                           el.getAttribute('data-parent-field') || 
                           el.getAttribute('data-depends-on') || 
                           el.getAttribute('data-cascade-from') ||
                           el.getAttribute('data-master-field');
    if (explicitParent) {
        const root = el.getRootNode ? el.getRootNode() : document;
        const pEl = deepGetElementById(root, explicitParent) || deepQuerySelector(root, explicitParent);
        if (pEl) {
            return {
                is_dependent: true,
                parent_id: pEl.id || explicitParent,
                parent_label: getUniversalLabel(pEl, true) || explicitParent,
                parent_local_id: pEl.getAttribute('data-wp-id') || null,
                confidence: 'high',
                mechanism: 'explicit_attribute'
            };
        }
    }

    // Check ARIA controls reversed
    if (el.id) {
        const controller = document.querySelector('[aria-controls*="' + el.id + '"], [data-controls*="' + el.id + '"]');
        if (controller && controller !== el) {
            return {
                is_dependent: true,
                parent_id: controller.id || '',
                parent_label: getUniversalLabel(controller, true) || 'Parent Field',
                parent_local_id: controller.getAttribute('data-wp-id') || null,
                confidence: 'high',
                mechanism: 'aria_controls'
            };
        }
    }

    // Heuristic Context Linkage for Disabled or Empty Dropdowns / Picklists:
    const hasZeroOrOneOption = isSelect ? (el.options && el.options.length <= 1) : false;
    if (isDisabled || hasZeroOrOneOption) {
        const container = el.closest('tr, .rcmFormField, .form-group, fieldset, .sf-form-row, .row, div[class*="field"], div[class*="Row"]');
        if (container) {
            const allInp = Array.from(container.querySelectorAll('input:not([type="hidden"]), select, [role="combobox"]'));
            const myIdx = allInp.indexOf(el);
            let candidateParent = null;

            if (myIdx > 0) {
                candidateParent = allInp[myIdx - 1];
            } else if (container.previousElementSibling) {
                const prevInps = Array.from(container.previousElementSibling.querySelectorAll('input:not([type="hidden"]), select, [role="combobox"]'));
                if (prevInps.length > 0) {
                    candidateParent = prevInps[prevInps.length - 1];
                }
            }

            if (candidateParent && candidateParent !== el) {
                const pLbl = getUniversalLabel(candidateParent, true);
                const curLbl = getUniversalLabel(el, true);
                
                const curLower = (curLbl || '').toLowerCase();
                const pLower = (pLbl || '').toLowerCase();
                const isSemanticPair = (
                    (pLower.includes('country') && (curLower.includes('state') || curLower.includes('city') || curLower.includes('university') || curLower.includes('region') || curLower.includes('school') || curLower.includes('institution'))) ||
                    (pLower.includes('category') && curLower.includes('sub')) ||
                    (pLower.includes('make') && curLower.includes('model')) ||
                    (pLower.includes('region') && (curLower.includes('city') || curLower.includes('branch')))
                );

                if (isSemanticPair || isDisabled) {
                    return {
                        is_dependent: true,
                        parent_id: candidateParent.id || candidateParent.name || '',
                        parent_label: pLbl || 'Preceding Field',
                        parent_local_id: candidateParent.getAttribute('data-wp-id') || null,
                        confidence: isSemanticPair ? 'high' : 'medium',
                        mechanism: 'dom_proximity_and_semantics'
                    };
                }
            }
        }
    }

    return null;
}
"""
