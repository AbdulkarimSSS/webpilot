"""Isolated DOM script for setting form field values."""

from typing import Final

SET_FIELD_DOM_SCRIPT: Final[str] = """([target, val, typeHint, scopedParent]) => {
    let mode = 'contains';
    let rawTarget = (target || '').trim();
    if (rawTarget.startsWith('exact:')) { mode = 'exact'; rawTarget = rawTarget.slice(6).trim(); }
    else if (rawTarget.startsWith('re:') || rawTarget.startsWith('regex:')) { mode = 'regex'; rawTarget = rawTarget.split(':', 2)[1].trim(); }
    else if (rawTarget.startsWith('starts:') || rawTarget.startsWith('prefix:')) { mode = 'starts'; rawTarget = rawTarget.split(':', 2)[1].trim(); }
    else if (rawTarget.startsWith('ends:') || rawTarget.startsWith('suffix:')) { mode = 'ends'; rawTarget = rawTarget.split(':', 2)[1].trim(); }
    else if (rawTarget.startsWith('contains:')) { mode = 'contains'; rawTarget = rawTarget.slice(9).trim(); }

    const lowerTarget = rawTarget.toLowerCase();
    const hint = (typeHint || '').toLowerCase().trim();
    let targetRegex = null;
    if (mode === 'regex') {
        try { targetRegex = new RegExp(rawTarget, 'i'); } catch(e){}
    }

    let parentScope = document;
    if (scopedParent && String(scopedParent).trim()) {
        const spLower = String(scopedParent).trim().toLowerCase();
        const containers = Array.from(document.querySelectorAll('section, fieldset, details, tr, .rcmFormField, .rcmFormSection, .form-group, .accordion-item, div'));
        const matchedContainer = containers.find(c => {
            const h = c.querySelector('h1, h2, h3, h4, h5, legend, th, button, .rcmFormSectionTopBar, summary, strong');
            if (h && (h.innerText || '').toLowerCase().includes(spLower)) return true;
            return (c.getAttribute && c.getAttribute('aria-label') && c.getAttribute('aria-label').toLowerCase().includes(spLower));
        });
        if (matchedContainer) {
            if (matchedContainer.tagName === 'DETAILS' && !matchedContainer.hasAttribute('open')) {
                matchedContainer.setAttribute('open', '');
            }
            const toggleBtn = matchedContainer.querySelector('button.rcmFormSectionTopBar, [aria-expanded="false"], .accordion-button.collapsed');
            if (toggleBtn) {
                try { toggleBtn.click(); } catch(e){}
            }
            parentScope = matchedContainer;
        } else {
            return { success: false, reason: "Scoped parent '" + scopedParent + "' not found" };
        }
    }

    function checkText(candidate) {
        if (!candidate) return false;
        const lowerC = candidate.toLowerCase();
        if (mode === 'exact') return lowerC === lowerTarget;
        if (mode === 'starts') return lowerC.startsWith(lowerTarget);
        if (mode === 'ends') return lowerC.endsWith(lowerTarget);
        if (mode === 'regex') return targetRegex ? targetRegex.test(candidate) : false;
        return lowerC.includes(lowerTarget);
    }

    function matchElement(el) {
        if (!el) return false;
        if (rawTarget.startsWith('@') && el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.id && (el.id.toLowerCase() === lowerTarget || checkText(el.id))) return true;
        if (el.name && (el.name.toLowerCase() === lowerTarget || checkText(el.name))) return true;
        if (el.placeholder && checkText(el.placeholder)) return true;

        if (el.id) {
            const l = parentScope.querySelector ? parentScope.querySelector('label[for="' + el.id + '"]') : null;
            if (l && l.innerText && checkText(l.innerText)) return true;
        }
        const container = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, div') : null;
        if (container && container.innerText && checkText(container.innerText)) return true;
        return false;
    }

    let exactEl = null;
    if (rawTarget.startsWith('@')) {
        exactEl = parentScope.querySelector('[data-wp-id="' + rawTarget + '"]');
    }
    if (!exactEl) {
        exactEl = document.getElementById(rawTarget);
    }
    if (!exactEl && rawTarget.includes(':')) {
        exactEl = parentScope.querySelector ? parentScope.querySelector('[id="' + rawTarget + '"]') : null;
    }

    // 1. SELECT
    if (!hint || hint === 'select' || hint === 'dropdown') {
        const selects = Array.from(parentScope.querySelectorAll('select'));
        const targetSelect = exactEl && exactEl.tagName === 'SELECT' ? exactEl : selects.find(matchElement);
        if (targetSelect) {
            if (targetSelect.disabled || targetSelect.getAttribute('aria-disabled') === 'true') {
                return { success: false, type: 'select', id: targetSelect.id, reason: 'Field is disabled (awaiting dependency)' };
            }
            let valMode = 'smart';
            let rawVal = String(val).trim();
            if (rawVal.startsWith('@opt-')) { valMode = 'index'; rawVal = rawVal.replace('@opt-', '').trim(); }
            else if (rawVal.startsWith('text:')) { valMode = 'text'; rawVal = rawVal.slice(5).trim(); }
            else if (rawVal.startsWith('val:') || rawVal.startsWith('value:')) { valMode = 'value'; rawVal = rawVal.split(':', 2)[1].trim(); }
            else if (rawVal.startsWith('index:') || rawVal.startsWith('#')) { valMode = 'index'; rawVal = rawVal.replace(/^(index:|#)/, '').trim(); }
            else if (rawVal.startsWith('re:') || rawVal.startsWith('regex:')) { valMode = 'regex'; rawVal = rawVal.split(':', 2)[1].trim(); }

            const strVal = rawVal.toLowerCase();
            let optRegex = null;
            if (valMode === 'regex') {
                try { optRegex = new RegExp(rawVal, 'i'); } catch(e){}
            }

            if (valMode === 'index') {
                const idx = parseInt(rawVal, 10);
                if (idx > 0 && targetSelect.options.length >= idx) {
                    targetSelect.selectedIndex = idx - 1;
                    targetSelect.dispatchEvent(new Event('input', { bubbles: true }));
                    targetSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    return { success: true, type: 'select', id: targetSelect.id };
                }
            }

            if (targetSelect.multiple) {
                const parts = strVal.split(',').map(s => s.trim().toLowerCase());
                let matchedCount = 0;
                for (let opt of targetSelect.options) {
                    const optVal = opt.value.toLowerCase();
                    const optText = (opt.text || opt.innerText || '').toLowerCase();
                    if (parts.includes(optVal) || parts.some(p => p && (optText === p || optText.includes(p)))) {
                        opt.selected = true;
                        matchedCount++;
                    }
                }
                targetSelect.dispatchEvent(new Event('input', { bubbles: true }));
                targetSelect.dispatchEvent(new Event('change', { bubbles: true }));
                return { success: matchedCount > 0, type: 'select', id: targetSelect.id, multiple: true };
            }

            let matched = false;
            for (let opt of targetSelect.options) {
                const optVal = opt.value.toLowerCase();
                const optText = (opt.text || opt.innerText || '').toLowerCase();
                if (valMode === 'value' && optVal === strVal) {
                    targetSelect.value = opt.value;
                    matched = true;
                    break;
                } else if (valMode === 'regex' && optRegex && (optRegex.test(opt.text) || optRegex.test(opt.value))) {
                    targetSelect.value = opt.value;
                    matched = true;
                    break;
                } else if (valMode === 'text' && (optText === strVal || (opt.text || '').trim().toLowerCase() === strVal)) {
                    targetSelect.value = opt.value;
                    matched = true;
                    break;
                } else if (valMode === 'smart' && (optVal === strVal || optText.includes(strVal))) {
                    targetSelect.value = opt.value;
                    matched = true;
                    break;
                }
            }
            if (matched) {
                targetSelect.dispatchEvent(new Event('input', { bubbles: true }));
                targetSelect.dispatchEvent(new Event('change', { bubbles: true }));
                return { success: true, type: 'select', id: targetSelect.id };
            }
            let reason = 'Option not found';
            if (targetSelect.options.length <= 1) {
                reason = 'Dropdown is empty (options not loaded or awaiting parent field)';
            } else {
                const avail = Array.from(targetSelect.options).map(o => (o.text || '').trim()).filter(Boolean).slice(0, 5);
                reason = "Option '" + rawVal + "' not found in dropdown (available: " + avail.join(', ') + ")";
            }
            return { success: false, type: 'select', id: targetSelect.id, reason: reason };
        }
    }

    // 2. Picklist
    if (!hint || hint === 'picklist' || hint === 'combobox' || hint === 'dropdown') {
        const picklistInputs = Array.from(document.querySelectorAll('input')).filter(i => 
            i.id.endsWith(':_input') || i.getAttribute('role') === 'combobox' || (i.getAttribute('data-wp-id') && i.getAttribute('data-wp-id').startsWith('@drop-'))
        );
        const targetPicklist = (exactEl && picklistInputs.includes(exactEl)) ? exactEl : picklistInputs.find(matchElement);
        if (targetPicklist) {
            if (targetPicklist.disabled || targetPicklist.getAttribute('aria-disabled') === 'true') {
                return { success: false, type: 'picklist', id: targetPicklist.id, reason: 'Picklist is disabled (awaiting dependency)' };
            }
            const baseId = targetPicklist.id.replace(':_input', '');
            const btn = document.getElementById(baseId + ':_selectButton');
            return { success: false, type: 'picklist', id: targetPicklist.id, trigger_button: btn ? btn.id : null };
        }
    }

    // 3. Radio / Checkboxes
    if (!hint || hint === 'choice' || hint === 'radio' || hint === 'checkbox') {
        const choices = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"]'));
        const matchingChoices = choices.filter(c => matchElement(c) || (c.name && c.name.toLowerCase().includes(lowerTarget)));
        if (matchingChoices.length > 0) {
            const strVal = String(val).toLowerCase();
            // Handle multi-value checkbox group (e.g. "AI,Security")
            if (strVal.includes(',') && matchingChoices.some(c => c.type === 'checkbox')) {
                const parts = strVal.split(',').map(s => s.trim().toLowerCase());
                let checkedCount = 0;
                for (let c of matchingChoices) {
                    if (c.type !== 'checkbox') continue;
                    const cLabel = (c.value + ' ' + (c.nextSibling ? c.nextSibling.textContent : '') + ' ' + (c.parentElement ? c.parentElement.innerText : '')).toLowerCase();
                    if (parts.some(p => p && (c.value.toLowerCase() === p || cLabel.includes(p)))) {
                        c.checked = true;
                        c.dispatchEvent(new Event('change', { bubbles: true }));
                        c.dispatchEvent(new Event('click', { bubbles: true }));
                        checkedCount++;
                    }
                }
                if (checkedCount > 0) {
                    return { success: true, type: 'checkbox_group', id: matchingChoices[0].id || target, count: checkedCount };
                }
            }
            let chosen = null;
            for (let c of matchingChoices) {
                const cLabel = (c.value + ' ' + (c.nextSibling ? c.nextSibling.textContent : '') + ' ' + (c.parentElement ? c.parentElement.innerText : '')).toLowerCase();
                if (cLabel.includes(strVal) || c.value.toLowerCase() === strVal) {
                    chosen = c;
                    break;
                }
            }
            if (!chosen && matchingChoices.length === 1 && (val === true || strVal === 'yes' || strVal === 'true' || strVal === 'on')) {
                chosen = matchingChoices[0];
            }
            if (chosen) {
                chosen.checked = true;
                chosen.dispatchEvent(new Event('change', { bubbles: true }));
                chosen.dispatchEvent(new Event('click', { bubbles: true }));
                return { success: true, type: chosen.type, id: chosen.id };
            }
        }

        // Custom Radio Groups
        const customGroups = Array.from(document.querySelectorAll('[role="radiogroup"], .radioGroup, .rcmFormQuestionElement, .RCMFormField'));
        const matchingGroup = customGroups.find(g => (g.innerText || '').toLowerCase().includes(lowerTarget));
        if (matchingGroup) {
            const strVal = String(val).toLowerCase();
            const radioOptions = Array.from(matchingGroup.querySelectorAll('.globalRadio, [role="radio"], .radioCheck, .sfRadioInputField'));
            for (let opt of radioOptions) {
                const optText = (opt.innerText || '').trim().toLowerCase();
                if (optText === strVal || optText.startsWith(strVal)) {
                    const clickable = opt.querySelector('.radioCheck, [role="radio"], .radioContainer') || opt;
                    clickable.click();
                    return { success: true, type: 'custom_radio', id: opt.id || '', value: strVal };
                }
            }
        }
    }

    // 4. Text / Textarea
    if (!hint || hint === 'text' || hint === 'input' || hint === 'textarea' || hint === 'string' || hint === 'number') {
        const textInputs = Array.from(document.querySelectorAll('input, textarea')).filter(i => {
            const t = (i.type || '').toLowerCase();
            return !['radio', 'checkbox', 'file', 'hidden', 'submit', 'button'].includes(t);
        });
        const targetText = exactEl || textInputs.find(matchElement);
        if (targetText) {
            if (targetText.disabled || targetText.getAttribute('aria-disabled') === 'true') {
                return { success: false, type: targetText.tagName.toLowerCase(), id: targetText.id, reason: 'Field is disabled (awaiting dependency)' };
            }
            if (targetText.readOnly) {
                return { success: false, type: targetText.tagName.toLowerCase(), id: targetText.id, reason: 'Field is read-only' };
            }
            let toSet = String(val);
            if (targetText.maxLength > 0 && toSet.length > targetText.maxLength) {
                toSet = toSet.substring(0, targetText.maxLength);
            }
            // Invoke native prototype descriptor setter for React / controlled synthetic state
            try {
                const proto = Object.getPrototypeOf(targetText);
                const protoDesc = Object.getOwnPropertyDescriptor(proto, 'value');
                if (protoDesc && protoDesc.set) {
                    protoDesc.set.call(targetText, toSet);
                }
            } catch(e){}
            try {
                targetText.value = toSet;
            } catch(e){}
            targetText.dispatchEvent(new Event('input', { bubbles: true }));
            targetText.dispatchEvent(new Event('change', { bubbles: true }));
            targetText.dispatchEvent(new Event('blur', { bubbles: true }));
            return { success: true, type: targetText.tagName.toLowerCase(), id: targetText.id, value: toSet };
        }
    }

    // Diagnostic probe for candidate elements that exist but were not interactable
    try {
        const allCandidates = Array.from(document.querySelectorAll('input, select, textarea, [role="combobox"], [role="radiogroup"]'));
        const cand = allCandidates.find(matchElement);
        if (cand) {
            if (cand.offsetParent === null || (window.getComputedStyle && (window.getComputedStyle(cand).display === 'none' || window.getComputedStyle(cand).visibility === 'hidden'))) {
                return { success: false, reason: 'Field is hidden or collapsed in DOM', id: cand.id || '' };
            }
            if (cand.disabled || cand.getAttribute('aria-disabled') === 'true') {
                return { success: false, reason: 'Field is disabled (awaiting dependency)', id: cand.id || '' };
            }
            if (cand.readOnly) {
                return { success: false, reason: 'Field is read-only', id: cand.id || '' };
            }
        }
    } catch(e){}

    return { success: false, reason: 'No matching element found' };
}"""

