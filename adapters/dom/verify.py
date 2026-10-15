"""Isolated DOM script for DOM field value verification."""

from typing import Final
from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS

_VERIFY_LOGIC: Final[str] = r"""
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
    const lower = rawTarget.toLowerCase();

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

    function matchEl(el) {
        if (!el) return false;
        if (rawTarget.startsWith('@') && el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.getAttribute && el.getAttribute('data-wp-id') === rawTarget) return true;
        if (el.id && el.id.toLowerCase() === lower) return true;
        if (el.name && el.name.toLowerCase() === lower) return true;
        if (el.placeholder && el.placeholder.toLowerCase().includes(lower)) return true;
        if (el.getAttribute) {
            const ariaLbl = el.getAttribute('aria-label') || el.getAttribute('accessible-name') || el.getAttribute('title');
            if (ariaLbl && ariaLbl.toLowerCase().includes(lower)) return true;
        }
        const wc = resolveWebComponent(el);
        if (wc && wc.getAttribute) {
            const wcLbl = wc.getAttribute('accessible-name') || wc.getAttribute('aria-label') || wc.getAttribute('title') || wc.getAttribute('placeholder');
            if (wcLbl && wcLbl.toLowerCase().includes(lower)) return true;
        }
        if (el.id) {
            const root = el.getRootNode ? el.getRootNode() : document;
            try {
                const escId = (window.CSS && CSS.escape) ? CSS.escape(el.id) : el.id.replace(/(:|\.|\[|\]|,|=|@|"|\\)/g, "\\$1");
                const lbl = (root.querySelector ? root.querySelector('label[for="' + escId + '"]') : null) || document.querySelector('label[for="' + escId + '"]');
                if (lbl && lbl.innerText && lbl.innerText.toLowerCase().includes(lower)) return true;
            } catch(e) {}
        }
        const parentLbl = el.closest ? el.closest('label') : null;
        if (parentLbl && parentLbl.innerText && parentLbl.innerText.toLowerCase().includes(lower)) return true;
        if (el.previousElementSibling) {
            const prev = el.previousElementSibling;
            const pt = (prev.innerText || prev.textContent || '').trim().toLowerCase();
            if (pt && pt.length < 60 && pt.includes(lower)) return true;
        }
        const c = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, fieldset') : null;
        if (c && c !== el) {
            const header = c.querySelector('label, legend, .control-label, .field-label, th, dt, strong');
            if (header && header.innerText && header.innerText.toLowerCase().includes(lower)) return true;
        }
        return false;
    }

    let exactEl = null;
    if (rawTarget.startsWith('css=') || rawTarget.startsWith('css:') || rawTarget.startsWith('selector:') || rawTarget.startsWith('selector=') || rawTarget.startsWith('xpath=') || rawTarget.startsWith('xpath:') || rawTarget.startsWith('//')) {
        exactEl = deepQuerySelector(parentScope, rawTarget);
    }
    if (!exactEl && rawTarget.startsWith('@')) {
        const matched = deepQueryAll(parentScope, '[data-wp-id="' + rawTarget + '"]');
        if (matched.length > 0) exactEl = matched[0];
    }
    if (!exactEl) {
        exactEl = deepGetElementById(parentScope, rawTarget);
    }
    if (!exactEl && rawTarget.includes(':')) {
        const matched = deepQueryAll(parentScope, '[id="' + rawTarget + '"]');
        if (matched.length > 0) exactEl = matched[0];
    }
    if (!exactEl) {
        try {
            exactEl = deepQuerySelector(parentScope, rawTarget);
        } catch(e) {}
    }

    function checkValidity(el) {
        if (!el) return true;
        if (el.getAttribute && (el.getAttribute('aria-invalid') === 'true' || el.getAttribute('data-invalid') === 'true' || el.getAttribute('data-error') === 'true')) return false;
        try {
            if (el.validity && el.validity.valid === false) return false;
        } catch (e) {}
        const errClsRe = /\b(invalidInput|is-invalid|ng-invalid-server|Mui-error|ant-input-status-error|v-input--error|is-error|field-error|input-error)\b/;
        if (el.className && typeof el.className === 'string' && errClsRe.test(el.className)) return false;
        const wc = resolveWebComponent(el);
        if (wc) {
            if (wc.getAttribute && (wc.getAttribute('value-state') === 'Error' || wc.getAttribute('aria-invalid') === 'true' || wc.getAttribute('data-invalid') === 'true')) return false;
            if (wc.valueState === 'Error') return false;
            const fmtPattern = (wc.getAttribute && (wc.getAttribute('format-pattern') || wc.getAttribute('placeholder'))) || '';
            const curVal = String(wc.value || (wc.getAttribute && wc.getAttribute('value')) || '').trim();
            if (curVal !== '' && fmtPattern) {
                const norm = normalizeUniversalDate(curVal, fmtPattern);
                if (!norm.isValid) return false;
            }
        }
        if (el.id && el.id.endsWith('_datepicker') && window.juic && window.juic.Component && window.juic.Component._registry) {
            const jc = window.juic.Component._registry[el.id.replace('_datepicker', '')];
            if (jc) {
                if (jc._hasError === true || jc._invalid === true) return false;
                if (typeof jc._getFormattedValue === 'function' && jc._value && jc._getFormattedValue(jc._value) === 'INVALID') return false;
            }
        }
        const errMsgId = el.getAttribute ? (el.getAttribute('aria-errormessage') || '') : '';
        if (errMsgId) {
            const errEl = document.getElementById(errMsgId);
            if (errEl && (errEl.innerText || errEl.textContent || '').trim().length > 0 && errEl.offsetWidth > 0) return false;
        }
        const container = el.closest ? el.closest('.has-error, .is-invalid, .invalid-feedback, .Mui-error, .ant-form-item-has-error, .v-input--error, .is-error, [aria-invalid="true"], [data-invalid="true"]') : null;
        if (container && container !== el) {
            return false;
        }
        return true;
    }

    // 1. SELECT elements
    const selects = deepQueryAll(parentScope, 'select');
    const targetSelect = exactEl ? (exactEl.tagName === 'SELECT' ? exactEl : null) : selects.find(matchEl);
    if (targetSelect) {
        if (targetSelect.multiple) {
            const selOpts = Array.from(targetSelect.selectedOptions);
            const vals = selOpts.map(o => (o.value || '').trim()).filter(Boolean);
            const texts = selOpts.map(o => (o.text || o.innerText || '').trim()).filter(Boolean);
            return {
                found: true,
                type: 'select',
                multiple: true,
                value: vals.join(','),
                text: texts.join(','),
                is_invalid: !checkValidity(targetSelect)
            };
        }
        const val = (targetSelect.value || '').trim();
        const selOpt = targetSelect.selectedOptions && targetSelect.selectedOptions[0];
        const text = selOpt ? (selOpt.text || '').trim() : '';
        return {
            found: true,
            type: 'select',
            value: val,
            text: text,
            is_invalid: !checkValidity(targetSelect)
        };
    }

    // 2. Combobox / Picklist / ARIA listbox
    const picklistInputs = deepQueryAll(parentScope, 'input[role="combobox"], input[id$=":_input"], [role="combobox"], .rcmpaginatedselectinput');
    const targetPick = exactEl ? (picklistInputs.includes(exactEl) ? exactEl : null) : picklistInputs.find(matchEl);
    if (targetPick) {
        const v = (targetPick.value || targetPick.innerText || targetPick.getAttribute('aria-valuenow') || '').trim();
        let listText = '';
        const owns = targetPick.getAttribute('aria-owns') || targetPick.getAttribute('aria-controls');
        if (owns) {
            const list = document.getElementById(owns);
            if (list) {
                const sel = list.querySelector('[aria-selected="true"], .selected, .active');
                if (sel) listText = (sel.innerText || sel.title || '').trim();
            }
        }
        return {
            found: true,
            type: 'picklist',
            value: v,
            selected_text: listText,
            is_invalid: !checkValidity(targetPick)
        };
    }

    // 3. Checkboxes & Switches
    const checkboxes = deepQueryAll(parentScope, 'input[type="checkbox"], [role="checkbox"], [role="switch"]');
    if (!exactEl) {
        const targetCheckboxes = checkboxes.filter(c => matchEl(c) || (c.name && c.name.toLowerCase().includes(lower)));
        if (targetCheckboxes.length > 1) {
            const checkedVals = targetCheckboxes.filter(c => c.checked).map(c => (c.value || c.getAttribute('aria-label') || '').trim());
            return {
                found: true,
                type: 'checkbox_group',
                value: checkedVals.join(','),
                count: checkedVals.length
            };
        }
    }
    const targetCheckbox = exactEl
        ? ((exactEl.type === 'checkbox' || (exactEl.getAttribute && ['checkbox', 'switch'].includes(exactEl.getAttribute('role')))) ? exactEl : null)
        : checkboxes.find(matchEl);
    if (targetCheckbox) {
        const isChecked = targetCheckbox.checked === true ||
                          targetCheckbox.getAttribute('aria-checked') === 'true' ||
                          targetCheckbox.classList.contains('checked') ||
                          targetCheckbox.classList.contains('active') ||
                          targetCheckbox.classList.contains('switch--checked');
        let checkVal = (targetCheckbox.value || '').trim();
        if (targetCheckbox.getAttribute('role') === 'switch') {
            checkVal = isChecked ? 'on' : '';
        }
        return {
            found: true,
            type: targetCheckbox.getAttribute('role') === 'switch' ? 'switch' : 'checkbox',
            checked: isChecked,
            value: checkVal,
            is_invalid: !checkValidity(targetCheckbox)
        };
    }

    // 4. Radios & Radio Groups
    const radios = deepQueryAll(parentScope, 'input[type="radio"], [role="radio"]');
    const matchingRadios = exactEl ? [] : radios.filter(r => matchEl(r) || (r.name && r.name.toLowerCase() === lower));
    const targetRadio = exactEl
        ? ((exactEl.type === 'radio' || (exactEl.getAttribute && exactEl.getAttribute('role') === 'radio')) ? exactEl : null)
        : (matchingRadios.find(r => r.checked) || matchingRadios[0]);
    if (targetRadio) {
        const isChecked = targetRadio.checked === true || targetRadio.getAttribute('aria-checked') === 'true';
        let radVal = (targetRadio.value || targetRadio.getAttribute('data-val') || '').trim();
        if (!radVal && isChecked) radVal = cleanStr(targetRadio.innerText || targetRadio.textContent, 'strip');
        return {
            found: true,
            type: 'radio',
            checked: isChecked,
            value: radVal,
            is_invalid: !checkValidity(targetRadio)
        };
    }

    if (!exactEl) {
        const groups = deepQueryAll(parentScope, '[role="radiogroup"], .radioGroup, fieldset, .rcmFormQuestionElement')
            .filter(g => g.querySelector('input[type="radio"], [role="radio"], .radioCheck, .globalRadio'));
        const grp = groups.find(matchEl);
        if (grp) {
            const checked = grp.querySelector('input[type="radio"]:checked, [role="radio"][aria-checked="true"], .radioCheck.checked, .globalRadio.selected');
            if (checked) {
                const val = checked.getAttribute('aria-label') || checked.getAttribute('data-val') || checked.value || (checked.parentElement ? checked.parentElement.innerText : '') || checked.innerText || 'checked';
                return {
                    found: true,
                    type: 'radio_group',
                    value: val.trim(),
                    is_invalid: !checkValidity(grp)
                };
            }
            return { found: true, type: 'radio_group', value: '', is_invalid: !checkValidity(grp) };
        }
    }

    // 5. Standard Inputs, Textareas, ContentEditable & Custom Web Components
    const textInputs = deepQueryAll(parentScope, 'input, textarea, [contenteditable="true"], [contenteditable=""], [contenteditable="plaintext-only"], [role="textbox"], [role="searchbox"], [role="spinbutton"], [role="slider"], *').filter(i => {
        const tag = (i.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea') {
            const t = (i.type || 'text').toLowerCase();
            return !['radio', 'checkbox', 'file', 'hidden', 'submit', 'button', 'reset'].includes(t);
        }
        if (i.isContentEditable || i.getAttribute('contenteditable') !== null) return true;
        const role = i.getAttribute('role');
        if (['textbox', 'searchbox', 'spinbutton', 'slider'].includes(role)) return true;
        if (isCustomElement(i)) return true;
        if (i.classList && (i.classList.contains('datePicker') || (i.id && i.id.includes('datepicker')))) return true;
        if (i.id) {
            const root = i.getRootNode ? i.getRootNode() : document;
            let hasLbl = false;
            try {
                const escId = (window.CSS && CSS.escape) ? CSS.escape(i.id) : i.id.replace(/(:|\.|\[|\]|,|=|@|"|\\)/g, "\\$1");
                hasLbl = !!((root.querySelector ? root.querySelector('label[for="' + escId + '"]') : null) || document.querySelector('label[for="' + escId + '"]'));
            } catch(e) {}
            if (hasLbl && !['select', 'button', 'a', 'label'].includes(tag)) return true;
        }
        return false;
    });

    let targetText = exactEl;
    if (!targetText) {
        const primaryInputs = textInputs.filter(i => {
            const tag = (i.tagName || '').toLowerCase();
            return tag === 'input' || tag === 'textarea' || i.isContentEditable || ['textbox', 'searchbox'].includes(i.getAttribute('role'));
        });
        targetText = primaryInputs.find(i => !isHoneypotOrHidden(i) && matchEl(i)) || primaryInputs.find(matchEl);
    }
    if (!targetText) {
        targetText = textInputs.find(i => !isHoneypotOrHidden(i) && matchEl(i)) || textInputs.find(matchEl);
    }
    if (targetText) {
        const tag = (targetText.tagName || '').toLowerCase();
        const wc = (tag !== 'input' && tag !== 'textarea' && !targetText.isContentEditable) ? resolveWebComponent(targetText) : null;
        const shadowInp = wc ? resolveShadowInput(targetText) : null;
        let v = (targetText.value || '').trim();
        if (!v && wc) {
            v = String(wc.value || (wc.getAttribute && wc.getAttribute('value')) || '').trim();
        }
        if (!v && shadowInp) {
            v = String(shadowInp.value || '').trim();
        }
        if (!v && (targetText.isContentEditable || targetText.getAttribute('contenteditable') !== null)) {
            v = String(targetText.textContent || targetText.innerText || '').trim();
        }
        if (!v) {
            if (targetText.getAttribute && targetText.getAttribute('data-state')) {
                v = targetText.getAttribute('data-state').trim();
            } else {
                try {
                    const proto = Object.getPrototypeOf(targetText);
                    const protoDesc = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (protoDesc && protoDesc.get) {
                        const pv = protoDesc.get.call(targetText);
                        if (pv) v = String(pv).trim();
                    }
                } catch(e){}
            }
        }

        // Also check if there is a connected hidden input in the same form (e.g. S03, S24, S41)
        if (!v && targetText.id) {
            const form = targetText.closest ? targetText.closest('form') : document;
            if (form) {
                const cleanId = targetText.id.replace(/-input|_input|_div|Div/g, '');
                const hid = form.querySelector('input[type="hidden"][name="' + cleanId + '"], input[type="hidden"][id="' + cleanId + '"]');
                if (hid && hid.value) v = hid.value.trim();
            }
        }

        return {
            found: true,
            type: wc ? 'date' : (targetText.isContentEditable ? 'contenteditable' : tag),
            value: v,
            is_invalid: !checkValidity(targetText)
        };
    }

    return null;
"""

VERIFY_FIELD_DOM_SCRIPT: Final[str] = "([target, expected]) => {\n" + UNIVERSAL_DOM_CORE_JS + "\n" + _VERIFY_LOGIC + "\n}"
