"""Isolated and parameterized DOM scripts evaluated in the browser context."""

from typing import Final

DETECT_LOGIN_PAGE_SCRIPT: Final[str] = """() => {
    const hasUser = document.querySelector('#username, input[type="email"], input[name="username"]');
    const hasPass = document.querySelector('#password, input[type="password"]');
    const title = document.title.toLowerCase();
    return !!(hasPass && (hasUser || title.includes('sign in') || title.includes('login')));
}"""

INJECT_LOGIN_CREDENTIALS_SCRIPT: Final[str] = """([u, p]) => {
    const userEl = document.querySelector('#username, input[type="email"], input[name="username"]');
    const passEl = document.querySelector('#password, input[type="password"]');
    if (userEl) {
        userEl.value = u;
        userEl.dispatchEvent(new Event('input', { bubbles: true }));
        userEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if (passEl) {
        passEl.value = p;
        passEl.dispatchEvent(new Event('input', { bubbles: true }));
        passEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
}"""

PORTAL_DROPDOWN_CLICK_SCRIPT: Final[str] = """() => {
    const toggle = document.querySelector('button.dropdown-toggle, .dropdown-toggle, [data-toggle="dropdown"]');
    if (toggle && toggle.offsetParent !== null) {
        toggle.click();
        return true;
    }
    return false;
}"""

PORTAL_APPLY_CLICK_SCRIPT: Final[str] = """() => {
    // 1. Prioritize inner manual apply option inside opened dropdown
    const manualOpt = document.querySelector('#applyOption-top-manual, .social-apply-option a, a.applyOption');
    if (manualOpt && manualOpt.offsetParent !== null) {
        manualOpt.click();
        return true;
    }

    // 2. Search for explicit apply buttons/links that are not dropdown toggles
    const links = Array.from(document.querySelectorAll('a, button, input[type="button"]'));
    const applyBtn = links.find(el => {
        if (el.classList.contains('dropdown-toggle')) return false;
        const t = (el.innerText || el.value || '').trim().toLowerCase();
        return t === 'apply now' || t === 'apply' || t === 'apply now »' || el.classList.contains('dialogApplyBtn');
    });
    if (applyBtn && applyBtn.offsetParent !== null) {
        applyBtn.click();
        return true;
    }
    return false;
}"""

CHECK_FORM_LOADING_SCRIPT: Final[str] = (
    "() => document.body.innerText.trim() === 'Loading...' || document.body.innerText.trim() === ''"
)

EXPAND_ALL_SECTIONS_SCRIPT: Final[str] = """() => {
    let count = 0;
    const sections = Array.from(document.querySelectorAll('.rcmFormSection, [class*="rcmFormSection"]'));
    for (let s of sections) {
        const btn = s.querySelector('button.rcmFormSectionTopBar, .rcmFormSectionTopBar');
        const content = s.querySelector('.sectionContent, [class*="sectionContent"]');
        const isClosed = (btn && btn.getAttribute('aria-expanded') === 'false') ||
                         (content && content.classList.contains('sectionContentClosed'));
        if (isClosed && btn) {
            btn.click();
            count++;
        }
    }
    return count;
}"""

INSPECT_PAGE_DOM_SCRIPT: Final[str] = """() => {
    const result = {
        title: document.title,
        url: window.location.href,
        buttons: [],
        dropdowns: [],
        inputs: [],
        choices: [],
        file_uploads: [],
        sections: [],
        already_uploaded_files: []
    };

    function clean(t) {
        if (!t) return '';
        return t.replace(/[\\u00a0\\r\\n\\t]+/g, ' ').replace(/^[\\s\\*]+/, '').trim();
    }

    function getLabel(el) {
        if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
        if (el.getAttribute('title')) return clean(el.getAttribute('title'));
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl && lbl.innerText) return clean(lbl.innerText);
        }
        const parentLbl = el.closest('label');
        if (parentLbl && parentLbl.innerText) return clean(parentLbl.innerText);

        const container = el.closest('tr, .rcmFormField, .form-group, .field, .row, div');
        if (container) {
            const lblEl = container.querySelector('label, .control-label, .field-label, th, dt, span.label, strong');
            if (lblEl && lblEl !== el && lblEl.innerText) {
                return clean(lblEl.innerText);
            }
            const text = container.innerText.trim().split('\\n')[0];
            if (text && text.length < 80) return clean(text);
        }
        return clean(el.placeholder || el.name || '');
    }

    function isRequired(el, labelText) {
        if (el.required || el.getAttribute('aria-required') === 'true') return true;
        const lower = (labelText || '').toLowerCase();
        if (lower.includes('*') || lower.includes('required')) return true;
        const container = el.closest('tr, .rcmFormField, .form-group, .field, div');
        if (container) {
            const reqMarker = container.querySelector('.required, .mandatory, [aria-hidden="false"]');
            if (reqMarker && (reqMarker.innerText || '').includes('*')) return true;
            if ((container.innerText || '').includes('*')) return true;
        }
        return false;
    }

    // 1. Sections
    const sectionTitles = Array.from(document.querySelectorAll('.rcmFormSectionTopBar, legend, h2, h3'))
        .map(el => clean(el.innerText))
        .filter(t => t.length > 2 && t.length < 80);
    result.sections = Array.from(new Set(sectionTitles));

    // 2. File Uploads
    const seenUploadLabels = new Set();
    const uploadNodes = Array.from(document.querySelectorAll('input[type="file"], .sfFileUpload, .fileUploadWrapper, [role="button"][id*="_attach"]'));
    uploadNodes.forEach(fi => {
        if (['LINK', 'SCRIPT', 'STYLE'].includes(fi.tagName)) return;
        const id = fi.id || '';
        if (id.includes('Deleting') || id.includes('Loading') || id.includes('Success') || 
            id.includes('aria') || id.includes('Date') || id.includes('Icon') || 
            id.includes('Form') || id.includes('Wrapper')) return;

        const rawLbl = getLabel(fi) || 'Document Upload';
        const lbl = clean(rawLbl.split('\\n')[0]);
        if (!lbl || seenUploadLabels.has(lbl.toLowerCase())) return;
        seenUploadLabels.add(lbl.toLowerCase());

        result.file_uploads.push({
            id: id,
            label: lbl,
            required: isRequired(fi, rawLbl)
        });
    });

    const docLinks = Array.from(document.querySelectorAll('.documentName, a[href*="download"], a[title*="Download"], span[title*=".pdf"]'))
        .map(a => clean(a.innerText || a.title))
        .filter(t => t.includes('.pdf') || t.includes('.doc') || t.includes('.docx'));
    result.already_uploaded_files = Array.from(new Set(docLinks));

    // 3. Dropdowns & Picklists
    document.querySelectorAll('select').forEach(sel => {
        if (sel.offsetParent === null) return;
        const lbl = getLabel(sel);
        result.dropdowns.push({
            id: sel.id || sel.name,
            label: lbl,
            type: 'select',
            required: isRequired(sel, lbl),
            value: sel.value || (sel.selectedOptions[0] ? clean(sel.selectedOptions[0].text) : '')
        });
    });

    const picklistInputs = Array.from(document.querySelectorAll('input')).filter(inp => 
        inp.id.endsWith(':_input') || inp.getAttribute('role') === 'combobox'
    );
    picklistInputs.forEach(pi => {
        const lbl = getLabel(pi);
        const baseId = pi.id.replace(':_input', '');
        const btn = document.getElementById(baseId + ':_selectButton');
        result.dropdowns.push({
            id: pi.id,
            trigger_id: btn ? btn.id : '',
            label: lbl,
            type: 'picklist',
            required: isRequired(pi, lbl),
            value: clean(pi.value)
        });
    });

    // 4. Choices (Radio / Checkbox Groups)
    const choiceGroups = {};
    const radios = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"], [role="radio"]'));
    radios.forEach(r => {
        const rg = r.closest('[role="radiogroup"], .rcmFormField, .form-group, tr, fieldset');
        let q = '';
        if (rg) {
            if (rg.getAttribute('aria-labelledby')) {
                const qNode = document.getElementById(rg.getAttribute('aria-labelledby'));
                if (qNode) q = clean(qNode.innerText);
            }
            if (!q) {
                const qEl = rg.querySelector('label, .rcmFormQuestionLabel, legend, strong');
                if (qEl) q = clean(qEl.innerText);
            }
        }
        if (!q && r.name) q = r.name;
        if (!q) return;

        let optLabel = clean(r.getAttribute('aria-label') || r.value || (r.parentElement ? r.parentElement.innerText : ''));
        if (!optLabel || optLabel.toLowerCase() === 'options') return;
        if (optLabel.length > 40) optLabel = optLabel.slice(0, 40);

        if (!choiceGroups[q]) {
            choiceGroups[q] = {
                question: q,
                type: (r.getAttribute('role') === 'radio' || r.type === 'radio') ? 'radio' : 'checkbox',
                required: isRequired(r, q),
                options: [],
                selected: null
            };
        }

        const isChecked = r.checked || r.getAttribute('aria-checked') === 'true' || r.classList.contains('radioOn');
        if (!choiceGroups[q].options.includes(optLabel)) {
            choiceGroups[q].options.push(optLabel);
        }
        if (isChecked) {
            choiceGroups[q].selected = optLabel;
        }
    });
    result.choices = Object.values(choiceGroups);

    // 5. Inputs
    const standardInputs = Array.from(document.querySelectorAll('input, textarea')).filter(el => {
        const t = (el.type || 'text').toLowerCase();
        if (['radio', 'checkbox', 'file', 'hidden', 'button', 'submit', 'reset'].includes(t)) return false;
        if (el.id.endsWith(':_input')) return false;
        if (el.getAttribute('role') === 'combobox') return false;
        if (el.offsetParent === null) return false;
        return true;
    });

    standardInputs.forEach(inp => {
        const lbl = getLabel(inp);
        if (!lbl) return;
        result.inputs.push({
            id: inp.id || inp.name,
            label: lbl,
            type: inp.type || inp.tagName.toLowerCase(),
            required: isRequired(inp, lbl),
            value: inp.value || ''
        });
    });

    // 6. Action Buttons
    const buttonEls = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a.btn, [role="button"], span[id$="_submitBtn"], span[id$="_saveBtn"]'));
    const seenButtons = new Set();
    buttonEls.forEach(btn => {
        if (btn.offsetParent === null) return;
        const id = btn.id || '';
        if (id.endsWith(':_selectButton')) return;
        const text = clean(btn.innerText || btn.value || btn.title);
        if (!text || text.length < 2 || text === '' || text === 'Options' || text === 'Menu') return;

        const lower = text.toLowerCase();
        let action = 'action';
        if (lower.includes('submit') || lower.includes('apply')) action = 'submit';
        else if (lower.includes('sign in') || lower.includes('log in') || lower.includes('login')) action = 'login';
        else if (lower.includes('start') || lower.includes('begin')) action = 'start';
        else if (lower.includes('save') || lower.includes('draft')) action = 'save';
        else if (lower.includes('next') || lower.includes('continue')) action = 'next';
        else if (lower.includes('back') || lower.includes('prev')) action = 'back';
        else if (lower.includes('expand')) action = 'expand_all';
        else if (lower.includes('collapse')) action = 'collapse_all';
        else if (lower.includes('add') || lower.includes('attach')) action = 'add_entry';
        else if (lower.includes('cancel') || lower.includes('close')) action = 'cancel';
        else action = 'button';

        const key = text + '_' + action;
        if (seenButtons.has(key)) return;
        seenButtons.add(key);

        result.buttons.push({
            id: id,
            text: text,
            action: action
        });
    });

    return result;
}"""

PROBE_PICKLIST_OPTIONS_SCRIPT: Final[str] = """(ownsId) => {
    let container = ownsId ? document.getElementById(ownsId) : null;
    if (!container) container = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist');
    const scope = container || document;
    const items = Array.from(scope.querySelectorAll('.globalMenuItem, li, [role="option"]'));
    return items.map(i => (i.innerText || '').trim()).filter(t => t.length > 0 && !t.includes('Loading') && !t.includes('Press Up'));
}"""

SET_FIELD_DOM_SCRIPT: Final[str] = """([target, val]) => {
    const lowerTarget = target.toLowerCase().trim();

    function matchElement(el) {
        if (el.id && el.id.toLowerCase() === lowerTarget) return true;
        if (el.name && el.name.toLowerCase() === lowerTarget) return true;
        if (el.placeholder && el.placeholder.toLowerCase().includes(lowerTarget)) return true;

        if (el.id) {
            const l = document.querySelector('label[for="' + el.id + '"]');
            if (l && l.innerText.toLowerCase().includes(lowerTarget)) return true;
        }
        const container = el.closest('tr, .rcmFormField, .form-group, .field, div');
        if (container && container.innerText.toLowerCase().includes(lowerTarget)) return true;
        return false;
    }

    let exactEl = document.getElementById(target);
    if (!exactEl && target.includes(':')) {
        exactEl = document.querySelector('[id="' + target + '"]');
    }

    // 1. SELECT
    const selects = Array.from(document.querySelectorAll('select'));
    const targetSelect = exactEl && exactEl.tagName === 'SELECT' ? exactEl : selects.find(matchElement);
    if (targetSelect) {
        const strVal = String(val).toLowerCase();
        let matched = false;
        for (let opt of targetSelect.options) {
            if (opt.value.toLowerCase() === strVal || opt.text.toLowerCase().includes(strVal)) {
                targetSelect.value = opt.value;
                targetSelect.dispatchEvent(new Event('change', { bubbles: true }));
                matched = true;
                break;
            }
        }
        return { success: matched, type: 'select', id: targetSelect.id };
    }

    // 2. Picklist
    const picklistInputs = Array.from(document.querySelectorAll('input')).filter(i => 
        i.id.endsWith(':_input') || i.getAttribute('role') === 'combobox'
    );
    const targetPicklist = (exactEl && picklistInputs.includes(exactEl)) ? exactEl : picklistInputs.find(matchElement);
    if (targetPicklist) {
        const baseId = targetPicklist.id.replace(':_input', '');
        const btn = document.getElementById(baseId + ':_selectButton');
        return { success: false, type: 'picklist', id: targetPicklist.id, trigger_button: btn ? btn.id : null };
    }

    // 3. Radio / Checkboxes
    const choices = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"]'));
    const matchingChoices = choices.filter(c => matchElement(c) || (c.name && c.name.toLowerCase().includes(lowerTarget)));
    if (matchingChoices.length > 0) {
        const strVal = String(val).toLowerCase();
        let chosen = null;
        for (let c of matchingChoices) {
            const cLabel = (c.value + ' ' + (c.nextSibling ? c.nextSibling.textContent : '') + ' ' + (c.parentElement ? c.parentElement.innerText : '')).toLowerCase();
            if (cLabel.includes(strVal) || c.value.toLowerCase() === strVal) {
                chosen = c;
                break;
            }
        }
        if (!chosen && matchingChoices.length === 1 && (val === true || strVal === 'yes' || strVal === 'true')) {
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

    // 4. Text / Textarea
    const textInputs = Array.from(document.querySelectorAll('input, textarea')).filter(i => {
        const t = (i.type || '').toLowerCase();
        return !['radio', 'checkbox', 'file', 'hidden', 'submit', 'button'].includes(t);
    });
    const targetText = exactEl || textInputs.find(matchElement);
    if (targetText) {
        let toSet = String(val);
        if (targetText.maxLength > 0 && toSet.length > targetText.maxLength) {
            toSet = toSet.substring(0, targetText.maxLength);
        }
        targetText.value = toSet;
        targetText.dispatchEvent(new Event('input', { bubbles: true }));
        targetText.dispatchEvent(new Event('change', { bubbles: true }));
        targetText.dispatchEvent(new Event('blur', { bubbles: true }));
        return { success: true, type: targetText.tagName.toLowerCase(), id: targetText.id, value: toSet };
    }

    return { success: false, reason: 'No matching element found' };
}"""

PICKLIST_AUTO_SCROLL_SCRIPT: Final[str] = """async ([inpId, target]) => {
    const input = document.getElementById(inpId);
    const owns = input ? input.getAttribute('aria-owns') : null;
    const list = owns ? document.getElementById(owns) : null;
    if (!list) return { success: false, reason: 'no list container' };

    const targetLower = String(target).trim().toLowerCase();
    const scrollParent = list.closest('.scroll, .scrolling, div[style*="overflow"]') || list.parentElement;

    for (let scrollStep = 0; scrollStep < 5; scrollStep++) {
        const items = Array.from(list.querySelectorAll('a, li'));
        const match = items.find(el => {
            const title = (el.getAttribute('title') || '').trim().toLowerCase();
            const text = (el.innerText || '').trim().toLowerCase();
            return title === targetLower || text === targetLower ||
                   (targetLower.length > 3 && (title.includes(targetLower) || text.includes(targetLower)));
        });

        if (match) {
            match.click();
            return { success: true, text: match.getAttribute('title') || match.innerText };
        }

        if (scrollParent) {
            scrollParent.scrollTop = scrollParent.scrollHeight;
            scrollParent.dispatchEvent(new Event('scroll', { bubbles: true }));
            await new Promise(r => setTimeout(r, 450));
        } else {
            break;
        }
    }

    return { success: false, reason: 'not found' };
}"""

VERIFY_FIELD_DOM_SCRIPT: Final[str] = """([target, expected]) => {
    const lower = target.toLowerCase().trim();
    function matchEl(el) {
        if (el.id && el.id.toLowerCase() === lower) return true;
        if (el.name && el.name.toLowerCase() === lower) return true;
        if (el.placeholder && el.placeholder.toLowerCase().includes(lower)) return true;
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl && lbl.innerText.toLowerCase().includes(lower)) return true;
        }
        const c = el.closest('tr, .rcmFormField, .form-group, div');
        if (c && c.innerText.toLowerCase().includes(lower)) return true;
        return false;
    }

    const junk = new Set(['login/ view profile', 'no selection', '']);
    const pick = Array.from(document.querySelectorAll('input[role="combobox"], input[id$=":_input"]')).find(matchEl);
    if (pick) {
        const v = (pick.value || '').trim().toLowerCase();
        if (v && !junk.has(v)) return v;
        return null;
    }

    const inp = Array.from(document.querySelectorAll('input, textarea'))
        .filter(i => !['radio','checkbox','file','hidden','submit','button'].includes((i.type||'').toLowerCase()))
        .find(matchEl);
    if (inp) return (inp.value || '').trim() || null;

    const groups = Array.from(document.querySelectorAll('[role="radiogroup"], .radioGroup'));
    const grp = groups.find(g => (g.innerText||'').toLowerCase().includes(lower));
    if (grp) {
        const checked = grp.querySelector('[aria-checked="true"], input[type="radio"]:checked');
        if (checked) {
            return checked.getAttribute('aria-label') || checked.value || 'checked';
        }
        const selectedRadio = Array.from(grp.querySelectorAll('.globalRadio')).find(r => {
            const span = r.querySelector('.radioCheck');
            return span && (span.classList.contains('checked') || span.classList.contains('selected') ||
                            r.getAttribute('aria-checked') === 'true');
        });
        if (selectedRadio) return (selectedRadio.innerText||'').trim().toLowerCase() || 'checked';
    }

    return null;
}"""

CLICK_BUTTON_DOM_SCRIPT: Final[str] = """(t) => {
    const lower = t.toLowerCase().trim();
    const direct = document.getElementById(t);
    if (direct) { direct.click(); return true; }

    const btns = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], a, [role="button"], span[id$="_submitBtn"], span[id$="_saveBtn"], .modal-footer *, .modal-close, [class*="close"], [aria-label*="close" i], p, span'));
    let chosen = btns.find(b => {
        const text = (b.innerText || b.value || b.title || '').trim().toLowerCase();
        return text === lower || (b.id && b.id.toLowerCase() === lower);
    });
    if (!chosen) {
        chosen = btns.find(b => {
            const text = (b.innerText || b.value || b.title || b.id || '').trim().toLowerCase();
            return text.includes(lower);
        });
    }
    if (chosen) {
        chosen.click();
        return true;
    }
    return false;
}"""
