"""Isolated DOM script for element probing and diagnostic metadata inspection."""

from typing import Final
from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS

_PROBE_LOGIC: Final[str] = r"""
    let rawTarget = (target || '').trim();
    if (/^(text|picklist|select|combobox|radio|checkbox|choice|input|textarea|date|datepicker|switch|contenteditable):/i.test(rawTarget)) {
        rawTarget = rawTarget.slice(rawTarget.indexOf(':') + 1).trim();
    }
    let scopedParent = null;
    if (rawTarget.includes('>>')) {
        const parts = rawTarget.split('>>').map(s => s.trim()).filter(Boolean);
        if (parts.length >= 2) {
            scopedParent = parts.slice(0, -1).join(' >> ');
            rawTarget = parts[parts.length - 1];
        }
    } else if (rawTarget.includes(' > ')) {
        const parts = rawTarget.split(' > ').map(s => s.trim()).filter(Boolean);
        if (parts.length >= 2) {
            scopedParent = parts.slice(0, -1).join(' > ');
            rawTarget = parts[parts.length - 1];
        }
    }
    const lowerTarget = rawTarget.toLowerCase();

    let parentScope = document;
    if (scopedParent) {
        const spLower = scopedParent.toLowerCase();
        const containers = deepQueryAll(document, 'section, fieldset, details, tr, .rcmFormField, .rcmFormSection, .form-group, .accordion-item, div');
        const matchedContainer = containers.find(c => {
            const h = c.querySelector('h1, h2, h3, h4, h5, legend, th, button, .rcmFormSectionTopBar, summary, strong');
            if (h && (h.innerText || '').toLowerCase().includes(spLower)) return true;
            return (c.getAttribute && c.getAttribute('aria-label') && c.getAttribute('aria-label').toLowerCase().includes(spLower));
        });
        if (matchedContainer) parentScope = matchedContainer;
    }

    function matchElement(el) {
        if (!el || !lowerTarget) return false;
        if (rawTarget.startsWith('@') && el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.id && el.id.toLowerCase() === lowerTarget) return true;
        if (el.name && el.name.toLowerCase() === lowerTarget) return true;
        if (el.placeholder && el.placeholder.toLowerCase().includes(lowerTarget)) return true;
        if (el.getAttribute) {
            const ariaLbl = el.getAttribute('aria-label') || el.getAttribute('accessible-name') || el.getAttribute('title');
            if (ariaLbl && ariaLbl.toLowerCase().includes(lowerTarget)) return true;
        }
        const wc = resolveWebComponent(el);
        if (wc && wc.getAttribute) {
            const wcLbl = wc.getAttribute('accessible-name') || wc.getAttribute('aria-label') || wc.getAttribute('title') || wc.getAttribute('placeholder');
            if (wcLbl && wcLbl.toLowerCase().includes(lowerTarget)) return true;
        }
        if (el.id) {
            const root = el.getRootNode ? el.getRootNode() : document;
            try {
                const escId = (window.CSS && CSS.escape) ? CSS.escape(el.id) : el.id.replace(/(:|\.|\[|\]|,|=|@|"|\\)/g, "\\$1");
                const l = (root.querySelector ? root.querySelector('label[for="' + escId + '"]') : null) || document.querySelector('label[for="' + escId + '"]');
                if (l && l.innerText && l.innerText.toLowerCase().includes(lowerTarget)) return true;
            } catch(e) {}
        }
        const container = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, td, fieldset') : null;
        if (container && container.innerText && container.innerText.toLowerCase().includes(lowerTarget)) return true;
        return false;
    }

    let el = null;
    const explicitSelector = (typeof selector !== 'undefined' && selector) ? String(selector).trim() : '';
    if (explicitSelector) {
        el = deepQuerySelector(parentScope, explicitSelector);
    }
    if (!el && (rawTarget.startsWith('css=') || rawTarget.startsWith('css:') || rawTarget.startsWith('selector:') || rawTarget.startsWith('selector=') || rawTarget.startsWith('xpath=') || rawTarget.startsWith('xpath:') || rawTarget.startsWith('//'))) {
        el = deepQuerySelector(parentScope, rawTarget);
    }
    if (!el && rawTarget.startsWith('@')) {
        const matched = deepQueryAll(parentScope, '[data-wp-id="' + rawTarget + '"]');
        if (matched.length > 0) el = matched[0];
    }
    if (!el) {
        el = deepGetElementById(parentScope, rawTarget);
    }
    if (!el && rawTarget.includes(':')) {
        const matched = deepQueryAll(parentScope, '[id="' + rawTarget + '"]');
        if (matched.length > 0) el = matched[0];
    }
    if (!el) {
        try {
            el = deepQuerySelector(parentScope, rawTarget);
        } catch(e) {}
    }
    if (!el) {
        const candidates = deepQueryAll(parentScope, 'input:not([type="hidden"]), select, textarea, button, [role="button"], [role="combobox"], [role="radiogroup"], [contenteditable="true"], [contenteditable=""], [role="textbox"], [role="switch"], *').filter(c => {
            const t = (c.tagName || '').toLowerCase();
            if (['script', 'style', 'head', 'link'].includes(t)) return false;
            return true;
        });
        el = candidates.find(c => !isHoneypotOrHidden(c) && matchElement(c)) || candidates.find(matchElement);
    }

    if (!el) {
        return { found: false, target: explicitSelector || rawTarget, reason: 'Element not found in DOM' };
    }

    const tag = (el.tagName || '').toLowerCase();
    const wpId = (el.getAttribute && el.getAttribute('data-wp-id')) || '';
    const isSectionContainer = wpId.startsWith('@sec-') || 
        ['section', 'form', 'fieldset', 'details', 'article', 'main'].includes(tag) ||
        (el.classList && (el.classList.contains('rcmFormSection') || el.classList.contains('form-section'))) ||
        (el.getAttribute && el.getAttribute('role') === 'region');

    let widgetType = 'input';
    let wc = null;
    let shadowInp = null;
    let isDatePicker = false;
    let label = '';

    if (isSectionContainer) {
        widgetType = wpId.startsWith('@sec-') || tag === 'section' || (el.classList && el.classList.contains('rcmFormSection')) ? 'section' : 'container';
        const headingEl = el.querySelector ? el.querySelector('h1, h2, h3, h4, h5, h6, legend, .accordion-header, .rcmFormSectionHeader, .rcmFormSectionTopBar, summary, [role="heading"], th') : null;
        if (headingEl) {
            label = (headingEl.innerText || headingEl.textContent || '').trim();
        } else {
            label = (el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('title'))) || '';
        }
    } else {
        wc = (tag !== 'input' && tag !== 'select' && tag !== 'textarea' && tag !== 'button' && !el.isContentEditable) ? (resolveWebComponent(el) || el) : null;
        shadowInp = wc ? resolveShadowInput(el) : null;
        const elType = (el.type || el.getAttribute('role') || tag).toLowerCase();
        const fmt = (wc && wc.getAttribute && (wc.getAttribute('format-pattern') || wc.getAttribute('placeholder'))) || el.getAttribute('placeholder') || '';
        isDatePicker = el.classList.contains('datePicker') || (el.id && el.id.includes('datepicker')) || (wc && (wc.tagName || '').toLowerCase().includes('date')) || (fmt && (fmt.toLowerCase().includes('dd/mm') || fmt.toLowerCase().includes('yyyy-mm')));
        if (isDatePicker) widgetType = 'date';
        else if (tag === 'select') widgetType = 'select';
        else if (el.id && el.id.endsWith(':_input')) widgetType = 'picklist';
        else if (elType === 'combobox') widgetType = 'picklist';
        else if (elType === 'radio') widgetType = 'radio';
        else if (elType === 'checkbox') widgetType = 'checkbox';
        else if (elType === 'switch') widgetType = 'switch';
        else if (el.isContentEditable || el.getAttribute('contenteditable') !== null) widgetType = 'contenteditable';
        else if (tag === 'button' || elType === 'button' || elType === 'submit') widgetType = 'button';

        label = getUniversalLabel(el, false);
    }

    let optionsList = [];
    if (includeOptions) {
        if (widgetType === 'select') {
            optionsList = Array.from(el.options || []).map((o, idx) => ({
                local_id: '@opt-' + (idx + 1),
                text: (o.text || '').trim(),
                value: (o.value || '').trim()
            }));
        } else if (widgetType === 'picklist') {
            const baseId = el.id ? el.id.replace(':_input', '') : '';
            const owns = el.getAttribute('aria-owns') || el.getAttribute('aria-controls') || '';
            const root = el.getRootNode ? el.getRootNode() : document;
            let list = owns ? ((root.getElementById ? root.getElementById(owns) : null) || document.getElementById(owns)) : null;
            if (!list && baseId) list = (root.getElementById ? root.getElementById(baseId + ':_listSelect') : null) || document.getElementById(baseId + ':_listSelect');
            if (!list && !owns) list = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"]), .globalMenu:not([style*="display: none"])');
            if (list) {
                const searchRoot = list.closest('.globalMenu, .sf-combo-listselect') || list;
                const rawItems = Array.from(searchRoot.querySelectorAll('a, li, [role="option"], [role="menuitem"], .globalMenuItem, .picklistOption, .rcmpaginatedselectitem, [class*="selectItem"]'));
                const items = rawItems.filter(item => !rawItems.some(other => other !== item && item.contains(other)));
                optionsList = items.map((i, idx) => ({
                    local_id: '@opt-' + (idx + 1),
                    text: (i.getAttribute('title') || i.innerText || i.textContent || '').trim(),
                    value: (i.getAttribute('data-value') || i.value || '').trim(),
                    id: i.id || ''
                })).filter(x => x.text.length > 0 && !x.text.includes('Loading') && !x.text.includes('Press Up'));
            }
        }
        if (queryFilter) {
            let regex = null;
            try {
                const matchRegex = queryFilter.match(/^\/(.+)\/([gimsuy]*)$/);
                if (matchRegex) {
                    regex = new RegExp(matchRegex[1], matchRegex[2]);
                } else {
                    regex = new RegExp(queryFilter, 'i');
                }
            } catch(e) {
                regex = null;
            }

            const qLower = queryFilter.toLowerCase();
            optionsList = optionsList.filter(o => {
                if (regex) {
                    try {
                        if (regex.test(o.text) || (o.value && regex.test(o.value)) || (o.local_id && regex.test(o.local_id))) {
                            return true;
                        }
                    } catch(e) {}
                }
                return o.text.toLowerCase().includes(qLower) || 
                       (o.value && o.value.toLowerCase().includes(qLower)) || 
                       (o.local_id && o.local_id.toLowerCase().includes(qLower));
            });
        }
    }

    const trigBtn = el.id && el.id.endsWith(':_input') ? document.getElementById(el.id.replace(':_input', ':_selectButton')) : null;

    let targetEl = el;
    let currentDepth = 0;
    let requestedUp = 0;
    if (typeof upLevels === 'string' && (upLevels.toLowerCase() === 'max' || upLevels.toLowerCase() === 'full' || upLevels.toLowerCase() === 'all' || upLevels.toLowerCase() === 'root')) {
        requestedUp = 9999;
    } else {
        requestedUp = parseInt(upLevels, 10) || 0;
    }

    let isMaxReached = false;
    while (currentDepth < requestedUp && targetEl && targetEl.parentElement) {
        const nextParent = targetEl.parentElement;
        const pTag = (nextParent.tagName || '').toLowerCase();
        targetEl = nextParent;
        currentDepth++;
        if (pTag === 'html' || nextParent === document.documentElement || !nextParent.parentElement) {
            isMaxReached = true;
            break;
        }
    }
    if (targetEl && (!targetEl.parentElement || targetEl === document.documentElement || (targetEl.tagName || '').toLowerCase() === 'html')) {
        isMaxReached = true;
    }

    try {
        deepQueryAll(document, '[data-wp-probe-target]').forEach(n => n.removeAttribute('data-wp-probe-target'));
        if (targetEl && targetEl.setAttribute) {
            targetEl.setAttribute('data-wp-probe-target', '1');
        }
    } catch(e) {}

    let bbox = null;
    try {
        if (targetEl && targetEl.getBoundingClientRect) {
            const r = targetEl.getBoundingClientRect();
            bbox = {
                x: Math.round(r.x),
                y: Math.round(r.y),
                width: Math.round(r.width),
                height: Math.round(r.height)
            };
        }
    } catch(e) {}

    let htmlOut = undefined;
    if (includeHtml || requestedUp > 0) {
        htmlOut = (targetEl && targetEl.outerHTML) || el.outerHTML || '';
        if (requestedUp === 0) {
            const ownsId = el.getAttribute('aria-owns') || el.getAttribute('aria-controls') || '';
            const listEl = ownsId ? document.getElementById(ownsId) : null;
            if (listEl && listEl.outerHTML) {
                htmlOut += '\n<!-- LIST_HTML -->\n' + listEl.outerHTML.slice(0, 1200);
            }
        }
    }

    let curVal = '';
    if (!isSectionContainer) {
        curVal = (el.value !== undefined && el.value !== '') ? el.value : '';
        if (!curVal && wc) {
            curVal = wc.value || (wc.getAttribute && wc.getAttribute('value')) || '';
        }
        if (!curVal && shadowInp) {
            curVal = shadowInp.value || '';
        }
        if (!curVal && (el.isContentEditable || el.getAttribute('contenteditable') !== null)) {
            curVal = el.textContent || el.innerText || '';
        }
        if (!curVal && el.value === undefined && !wc) {
            curVal = el.innerText || '';
        }
    }

    let isReq = false;
    if (!isSectionContainer) {
        isReq = Boolean(el.required || el.getAttribute('aria-required') === 'true' || (wc && (wc.required || wc.getAttribute('required') !== null || wc.getAttribute('aria-required') === 'true')));
        if (!isReq && el.id) {
            const root = el.getRootNode ? el.getRootNode() : document;
            const l = (root.querySelector ? root.querySelector('label[for="' + el.id + '"]') : null) || document.querySelector('label[for="' + el.id + '"]');
            if (l && ((l.innerText || '').includes('*') || l.querySelector('.required, .requiredField, .mandatory'))) isReq = true;
            if (el.id.endsWith('_datepicker') && window.juic && window.juic.Component && window.juic.Component._registry) {
                const jc = window.juic.Component._registry[el.id.replace('_datepicker', '')];
                if (jc && jc._isRequired) isReq = true;
            }
        }
    }

    const dep = detectDependentParentField(el);

    return {
        found: true,
        local_id: el.getAttribute('data-wp-id') || '',
        id: el.id || '',
        name: el.name || '',
        tag: tag,
        type: widgetType,
        input_type: isSectionContainer ? '' : (isDatePicker ? 'date' : (el.type || '')),
        format_pattern: (wc && wc.getAttribute && (wc.getAttribute('format-pattern') || wc.getAttribute('placeholder'))) || '',
        label: label,
        value: curVal,
        required: isReq,
        disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true' || (wc && (wc.disabled || wc.getAttribute('disabled') !== null))),
        visible: !isHoneypotOrHidden(el),
        trigger_button: trigBtn ? trigBtn.id : null,
        owns_id: el.getAttribute('aria-owns') || el.getAttribute('aria-controls') || '',
        dependency: dep,
        options_count: optionsList.length,
        options: optionsList,
        ancestor_depth: currentDepth,
        ancestor_requested: requestedUp,
        ancestor_max_reached: isMaxReached,
        ancestor_tag: targetEl ? (targetEl.tagName || '').toLowerCase() : tag,
        ancestor_id: targetEl ? (targetEl.id || '') : (el.id || ''),
        ancestor_class: targetEl ? (targetEl.className || '') : '',
        bounding_box: bbox,
        outerHTML: htmlOut,
        html: htmlOut
    };
"""

PROBE_FIELD_DOM_SCRIPT: Final[str] = "([target, includeOptions = false, queryFilter = '', includeHtml = false, upLevels = 0, selector = '']) => {\n" + UNIVERSAL_DOM_CORE_JS + "\n" + _PROBE_LOGIC + "\n}"
