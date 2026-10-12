"""Isolated DOM script for element probing and diagnostic metadata inspection."""

from typing import Final

PROBE_FIELD_DOM_SCRIPT: Final[str] = """([target, includeOptions = false, queryFilter = '', includeHtml = false]) => {
    const rawTarget = (target || '').trim();
    const lowerTarget = rawTarget.toLowerCase();

    function matchElement(el) {
        if (!el) return false;
        if (rawTarget.startsWith('@') && el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.id && el.id.toLowerCase() === lowerTarget) return true;
        if (el.name && el.name.toLowerCase() === lowerTarget) return true;
        if (el.placeholder && el.placeholder.toLowerCase().includes(lowerTarget)) return true;
        if (el.getAttribute && el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes(lowerTarget)) return true;
        if (el.id) {
            const l = document.querySelector('label[for="' + el.id + '"]');
            if (l && l.innerText && l.innerText.toLowerCase().includes(lowerTarget)) return true;
        }
        const container = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, td, fieldset') : null;
        if (container && container.innerText && container.innerText.toLowerCase().includes(lowerTarget)) return true;
        return false;
    }

    let el = null;
    if (rawTarget.startsWith('@')) {
        el = document.querySelector('[data-wp-id="' + rawTarget + '"]');
    }
    if (!el) {
        el = document.getElementById(rawTarget);
    }
    if (!el && rawTarget.includes(':')) {
        try { el = document.querySelector('[id="' + rawTarget + '"]'); } catch(e){}
    }
    if (!el) {
        const candidates = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea, button, [role="button"], [role="combobox"], [role="radiogroup"]'));
        el = candidates.find(c => c.offsetParent !== null && matchElement(c)) || candidates.find(matchElement);
    }

    if (!el) {
        return { found: false, target: rawTarget, reason: 'Element not found in DOM' };
    }

    const tag = (el.tagName || '').toLowerCase();
    const elType = (el.type || el.getAttribute('role') || tag).toLowerCase();
    let widgetType = 'input';
    if (tag === 'select') widgetType = 'select';
    else if (el.id && el.id.endsWith(':_input')) widgetType = 'picklist';
    else if (elType === 'combobox') widgetType = 'picklist';
    else if (elType === 'radio') widgetType = 'radio';
    else if (elType === 'checkbox') widgetType = 'checkbox';
    else if (tag === 'button' || elType === 'button' || elType === 'submit') widgetType = 'button';

    let label = '';
    if (el.getAttribute('aria-label')) label = el.getAttribute('aria-label').trim();
    if (!label && el.id) {
        const l = document.querySelector('label[for="' + el.id + '"]');
        if (l) label = (l.innerText || '').trim();
    }
    if (!label) {
        const c = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, div') : null;
        if (c) {
            const lblEl = c.querySelector('label, .control-label, .field-label, th, dt, strong');
            if (lblEl && lblEl !== el) label = (lblEl.innerText || '').trim();
        }
    }
    if (!label) label = (el.placeholder || el.title || el.name || '').trim();

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
            let list = owns ? document.getElementById(owns) : null;
            if (!list && baseId) list = document.getElementById(baseId + ':_listSelect');
            if (!list && !owns) list = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"]), .globalMenu:not([style*="display: none"])');
            if (list) {
                const searchRoot = list.closest('.globalMenu, .sf-combo-listselect') || list;
                const rawItems = Array.from(searchRoot.querySelectorAll('a, li, [role="option"], [role="menuitem"], .globalMenuItem, .picklistOption, .rcmpaginatedselectitem, [class*="selectItem"]'));
                // Deduplicate wrapper elements (e.g. keep inner <a> if wrapped by <li>)
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
            const q = queryFilter.toLowerCase();
            optionsList = optionsList.filter(o => o.text.toLowerCase().includes(q) || (o.value && o.value.toLowerCase().includes(q)) || (o.local_id && o.local_id.toLowerCase().includes(q)));
        }
    }

    const trigBtn = el.id && el.id.endsWith(':_input') ? document.getElementById(el.id.replace(':_input', ':_selectButton')) : null;

    let htmlOut = undefined;
    if (includeHtml) {
        htmlOut = el.outerHTML || '';
        const ownsId = el.getAttribute('aria-owns') || el.getAttribute('aria-controls') || '';
        const listEl = ownsId ? document.getElementById(ownsId) : null;
        if (listEl && listEl.outerHTML) {
            htmlOut += '\\n<!-- LIST_HTML -->\\n' + listEl.outerHTML.slice(0, 1200);
        }
    }

    return {
        found: true,
        local_id: el.getAttribute('data-wp-id') || '',
        id: el.id || '',
        name: el.name || '',
        tag: tag,
        type: widgetType,
        input_type: el.type || '',
        label: label,
        value: el.value !== undefined ? el.value : (el.innerText || ''),
        required: el.required || el.getAttribute('aria-required') === 'true',
        disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
        visible: el.offsetParent !== null,
        trigger_button: trigBtn ? trigBtn.id : null,
        owns_id: el.getAttribute('aria-owns') || el.getAttribute('aria-controls') || '',
        options_count: optionsList.length,
        options: optionsList,
        outerHTML: htmlOut,
        html: htmlOut
    };
}"""


