"""Isolated DOM script for DOM field value verification."""

from typing import Final

VERIFY_FIELD_DOM_SCRIPT: Final[str] = """([target, expected]) => {
    const lower = (target || '').toLowerCase().trim();
    function matchEl(el) {
        if (!el) return false;
        if (target.startsWith('@') && el.getAttribute && el.getAttribute('data-wp-id') === target) return true;
        if (el.getAttribute && el.getAttribute('data-wp-id') === target) return true;
        if (el.id && el.id.toLowerCase() === lower) return true;
        if (el.name && el.name.toLowerCase() === lower) return true;
        if (el.placeholder && el.placeholder.toLowerCase().includes(lower)) return true;
        if (el.getAttribute && el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes(lower)) return true;
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl && lbl.innerText && lbl.innerText.toLowerCase().includes(lower)) return true;
        }
        const parentLbl = el.closest ? el.closest('label') : null;
        if (parentLbl && parentLbl.innerText && parentLbl.innerText.toLowerCase().includes(lower)) return true;
        const c = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, fieldset, div') : null;
        if (c) {
            const header = c.querySelector('label, legend, .control-label, .field-label, th, dt, strong');
            if (header && header.innerText && header.innerText.toLowerCase().includes(lower)) return true;
            if (c.innerText && c.innerText.toLowerCase().includes(lower)) return true;
        }
        return false;
    }

    let exactEl = null;
    if (target.startsWith('@')) {
        exactEl = document.querySelector('[data-wp-id="' + target + '"]');
    }
    if (!exactEl) {
        exactEl = document.getElementById(target);
    }
    if (!exactEl && target.includes(':')) {
        try { exactEl = document.querySelector('[id="' + target + '"]'); } catch(e){}
    }

    const junk = new Set(['login/ view profile', 'no selection', 'select', 'choose', '-- select --', '']);

    function checkValidity(el) {
        if (!el) return true;
        if (el.getAttribute && (el.getAttribute('aria-invalid') === 'true' || el.getAttribute('data-invalid') === 'true' || el.getAttribute('data-error') === 'true')) return false;
        try {
            if (el.validity && el.validity.valid === false) return false;
        } catch (e) {}
        const errClsRe = /\\b(invalidInput|is-invalid|ng-invalid-server|Mui-error|ant-input-status-error|v-input--error|is-error|field-error|input-error)\\b/;
        if (el.className && typeof el.className === 'string' && errClsRe.test(el.className)) return false;
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
    const selects = Array.from(document.querySelectorAll('select'));
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
    const picklistInputs = Array.from(document.querySelectorAll('input[role="combobox"], input[id$=":_input"], [role="combobox"], .rcmpaginatedselectinput'));
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
    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"], [role="checkbox"], [role="switch"]'));
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
        return {
            found: true,
            type: 'checkbox',
            checked: isChecked,
            value: (targetCheckbox.value || '').trim(),
            is_invalid: !checkValidity(targetCheckbox)
        };
    }

    // 4. Radios & Radio Groups
    const radios = Array.from(document.querySelectorAll('input[type="radio"], [role="radio"]'));
    const matchingRadios = exactEl ? [] : radios.filter(r => matchEl(r) || (r.name && r.name.toLowerCase() === lower));
    const targetRadio = exactEl
        ? ((exactEl.type === 'radio' || (exactEl.getAttribute && exactEl.getAttribute('role') === 'radio')) ? exactEl : null)
        : (matchingRadios.find(r => r.checked) || matchingRadios[0]);
    if (targetRadio) {
        const isChecked = targetRadio.checked === true || targetRadio.getAttribute('aria-checked') === 'true';
        return {
            found: true,
            type: 'radio',
            checked: isChecked,
            value: (targetRadio.value || '').trim(),
            is_invalid: !checkValidity(targetRadio)
        };
    }

    if (!exactEl) {
        const groups = Array.from(document.querySelectorAll('[role="radiogroup"], .radioGroup, fieldset, .rcmFormQuestionElement'))
                            .filter(g => g.querySelector('input[type="radio"], [role="radio"], .radioCheck, .globalRadio'));
        const grp = groups.find(matchEl);
        if (grp) {
            const checked = grp.querySelector('input[type="radio"]:checked, [role="radio"][aria-checked="true"], .radioCheck.checked, .globalRadio.selected');
            if (checked) {
                const val = checked.getAttribute('aria-label') || checked.value || (checked.parentElement ? checked.parentElement.innerText : '') || checked.innerText || 'checked';
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


    // 5. Standard Inputs & Textareas
    const textInputs = Array.from(document.querySelectorAll('input, textarea')).filter(i => {
        const t = (i.type || 'text').toLowerCase();
        return !['radio', 'checkbox', 'file', 'hidden', 'submit', 'button', 'reset'].includes(t);
    });
    const targetText = exactEl || textInputs.find(matchEl);
    if (targetText) {
        let v = (targetText.value || '').trim();
        if (!v) {
            if (targetText.getAttribute('data-state')) {
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
        return {
            found: true,
            type: targetText.tagName.toLowerCase(),
            value: v,
            is_invalid: !checkValidity(targetText)
        };
    }

    return null;
}"""

