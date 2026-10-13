"""Isolated DOM scripts for page schema inspection and picklist option probing."""

from typing import Final
from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS

_INSPECT_LOGIC: Final[str] = r"""
    let puaMode = args && args.puaMode ? args.puaMode : null;
    if (!puaMode) {
        const sanitizePua = args && typeof args.sanitizePua === 'boolean' ? args.sanitizePua : true;
        puaMode = sanitizePua ? 'strip' : 'escape';
    }
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
        return cleanStr(t, puaMode);
    }

    function getLabel(el) {
        return getUniversalLabel(el, puaMode === 'strip');
    }

    function isRequired(el, labelText) {
        if (el.required || el.getAttribute('aria-required') === 'true') return true;
        const wc = resolveWebComponent(el);
        if (wc && (wc.required || wc.getAttribute('required') !== null || wc.getAttribute('aria-required') === 'true')) return true;
        if (el.id) {
            const root = el.getRootNode ? el.getRootNode() : document;
            const l = (root.querySelector ? root.querySelector('label[for="' + el.id + '"]') : null) || document.querySelector('label[for="' + el.id + '"]');
            if (l && ((l.innerText || '').includes('*') || l.querySelector('.required, .requiredField, .mandatory'))) return true;
            if (el.id.endsWith('_datepicker') && window.juic && window.juic.Component && window.juic.Component._registry) {
                const jc = window.juic.Component._registry[el.id.replace('_datepicker', '')];
                if (jc && jc._isRequired) return true;
            }
        }
        const lower = (labelText || '').toLowerCase();
        if (lower.includes('*') || lower.includes('required')) return true;
        const container = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field, div, fieldset') : null;
        if (container) {
            const reqMarker = container.querySelector('.required, .mandatory, [aria-hidden="false"]');
            if (reqMarker && (reqMarker.innerText || '').includes('*')) return true;
            if ((container.innerText || '').includes('*')) return true;
        }
        return false;
    }

    let fldCount = 0;
    let dropCount = 0;
    let optCount = 0;
    let upCount = 0;
    let btnCount = 0;

    // 1. Sections
    const sectionTitles = deepQueryAll(document, '.rcmFormSectionTopBar, legend, h2, h3, [role="heading"]')
        .map(el => clean(el.innerText || el.textContent))
        .filter(t => t.length > 2 && t.length < 80);
    result.sections = Array.from(new Set(sectionTitles));

    // 2. File Uploads
    const seenUploadLabels = new Set();
    const uploadNodes = deepQueryAll(document, 'input[type="file"], .sfFileUpload, .fileUploadWrapper, [role="button"][id*="_attach"]');
    uploadNodes.forEach(fi => {
        if (['LINK', 'SCRIPT', 'STYLE'].includes(fi.tagName)) return;
        const id = fi.id || '';
        if (id.includes('Deleting') || id.includes('Loading') || id.includes('Success') || 
            id.includes('aria') || id.includes('Date') || id.includes('Icon') || 
            id.includes('Form') || id.includes('Wrapper')) return;

        const rawLbl = getLabel(fi) || 'Document Upload';
        const lbl = clean(rawLbl.split('\n')[0]);
        if (!lbl || seenUploadLabels.has(lbl.toLowerCase())) return;
        seenUploadLabels.add(lbl.toLowerCase());

        upCount++;
        const localId = '@file-' + upCount;
        try { fi.setAttribute('data-wp-id', localId); } catch(e){}

        result.file_uploads.push({
            local_id: localId,
            id: id,
            label: lbl,
            required: isRequired(fi, rawLbl)
        });
    });

    const docLinks = deepQueryAll(document, '.documentName, a[href*="download"], a[title*="Download"], span[title*=".pdf"]')
        .map(a => clean(a.innerText || a.title))
        .filter(t => t.includes('.pdf') || t.includes('.doc') || t.includes('.docx'));
    result.already_uploaded_files = Array.from(new Set(docLinks));

    // 3. Dropdowns & Picklists
    const selectNodes = deepQueryAll(document, 'select');
    selectNodes.forEach(sel => {
        if (isHoneypotOrHidden(sel)) return;
        const lbl = getLabel(sel);
        dropCount++;
        const localId = '@drop-' + dropCount;
        try { sel.setAttribute('data-wp-id', localId); } catch(e){}

        result.dropdowns.push({
            local_id: localId,
            id: sel.id || sel.name,
            label: lbl,
            type: 'select',
            required: isRequired(sel, lbl),
            value: sel.value || (sel.selectedOptions && sel.selectedOptions[0] ? clean(sel.selectedOptions[0].text) : '')
        });
    });

    const picklistInputs = deepQueryAll(document, 'input').filter(inp => 
        inp.id.endsWith(':_input') || inp.getAttribute('role') === 'combobox' || (inp.getAttribute('aria-haspopup') === 'listbox')
    );
    picklistInputs.forEach(pi => {
        if (isHoneypotOrHidden(pi)) return;
        const lbl = getLabel(pi);
        const baseId = pi.id ? pi.id.replace(':_input', '') : '';
        const root = pi.getRootNode ? pi.getRootNode() : document;
        const btn = baseId ? (root.getElementById ? root.getElementById(baseId + ':_selectButton') : document.getElementById(baseId + ':_selectButton')) : null;
        dropCount++;
        const localId = '@drop-' + dropCount;
        try {
            pi.setAttribute('data-wp-id', localId);
            if (btn) btn.setAttribute('data-wp-id', localId + '-trigger');
        } catch(e){}

        result.dropdowns.push({
            local_id: localId,
            id: pi.id,
            trigger_id: btn ? btn.id : '',
            owns_id: pi.getAttribute('aria-owns') || pi.getAttribute('aria-controls') || '',
            label: lbl,
            type: 'picklist',
            required: isRequired(pi, lbl),
            value: clean(pi.value)
        });
    });

    // 4. Choices (Radio / Checkbox Groups & Switches)
    const choiceGroups = {};
    const choices = deepQueryAll(document, 'input[type="radio"], input[type="checkbox"], [role="radio"], [role="checkbox"], [role="switch"]');
    choices.forEach(r => {
        if (isHoneypotOrHidden(r)) return;
        const rg = r.closest ? r.closest('[role="radiogroup"], .rcmFormField, .form-group, tr, fieldset') : null;
        let q = '';
        if (rg) {
            if (rg.getAttribute('aria-labelledby')) {
                const root = rg.getRootNode ? rg.getRootNode() : document;
                const qNode = (root.getElementById ? root.getElementById(rg.getAttribute('aria-labelledby')) : null) || document.getElementById(rg.getAttribute('aria-labelledby'));
                if (qNode) q = clean(qNode.innerText || qNode.textContent);
            }
            if (!q) {
                const qEl = rg.querySelector('label, .rcmFormQuestionLabel, legend, strong');
                if (qEl) q = clean(qEl.innerText || qEl.textContent);
            }
        }
        if (!q && r.name) q = r.name;
        if (!q && r.getAttribute('aria-label')) q = r.getAttribute('aria-label');
        if (!q && r.id) {
            const root = r.getRootNode ? r.getRootNode() : document;
            const l = (root.querySelector ? root.querySelector('label[for="' + r.id + '"]') : null) || document.querySelector('label[for="' + r.id + '"]');
            if (l) q = clean(l.innerText);
        }
        if (!q && r.getAttribute('role') === 'switch') q = clean(r.innerText || r.textContent);
        if (!q) return;

        let optLabel = clean(r.getAttribute('aria-label') || r.value || (r.parentElement ? r.parentElement.innerText : ''));
        if (r.getAttribute('role') === 'switch') optLabel = clean(r.innerText || 'Toggle');
        if (!optLabel || optLabel.toLowerCase() === 'options') return;
        if (optLabel.length > 40) optLabel = optLabel.slice(0, 40);

        const rRole = r.getAttribute('role') || r.type || '';
        const isRadio = rRole === 'radio';
        const isSwitch = rRole === 'switch';

        if (!choiceGroups[q]) {
            optCount++;
            const localId = '@opt-' + optCount;
            choiceGroups[q] = {
                local_id: localId,
                id: r.id || r.name || q,
                name: r.name || r.id || q,
                label: q,
                question: q,
                type: isRadio ? 'radio' : (isSwitch ? 'switch' : 'checkbox'),
                required: isRequired(r, q),
                options: [],
                selected: null
            };
            try {
                if (rg) rg.setAttribute('data-wp-id', localId);
            } catch(e){}
        }

        try {
            r.setAttribute('data-wp-id', choiceGroups[q].local_id);
        } catch(e){}

        const isChecked = r.checked || r.getAttribute('aria-checked') === 'true' || r.classList.contains('radioOn') || r.classList.contains('checked');
        if (!choiceGroups[q].options.includes(optLabel)) {
            choiceGroups[q].options.push(optLabel);
        }
        if (isChecked) {
            choiceGroups[q].selected = optLabel;
        }
    });
    result.choices = Object.values(choiceGroups);

    // 5. Universal Inputs, Textareas, DatePickers & Custom Web Components
    const seenInputElements = new Set();
    const candidateInputs = [];

    // 5a. Deep standard inputs and textareas
    deepQueryAll(document, 'input, textarea').forEach(el => {
        const t = (el.type || 'text').toLowerCase();
        if (['radio', 'checkbox', 'file', 'hidden', 'button', 'submit', 'reset'].includes(t)) return;
        if (el.id && el.id.endsWith(':_input')) return;
        if (el.getAttribute('role') === 'combobox') return;
        if (isHoneypotOrHidden(el)) return;
        candidateInputs.push(el);
    });

    // 5b. ContentEditable & ARIA value roles
    deepQueryAll(document, '[contenteditable="true"], [contenteditable=""], [contenteditable="plaintext-only"], [role="textbox"], [role="searchbox"], [role="spinbutton"], [role="slider"]').forEach(el => {
        const tag = (el.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea') return;
        if (isHoneypotOrHidden(el)) return;
        candidateInputs.push(el);
    });

    // 5c. Custom Web Elements & Label-bound elements
    deepQueryAll(document, '*').forEach(el => {
        if (isCustomElement(el)) {
            if (isHoneypotOrHidden(el)) return;
            const tag = (el.tagName || '').toLowerCase();
            if (['select', 'button', 'a', 'form', 'style', 'script'].includes(tag)) return;
            candidateInputs.push(el);
        } else if (el.id) {
            const root = el.getRootNode ? el.getRootNode() : document;
            const hasLabel = !!((root.querySelector ? root.querySelector('label[for="' + el.id + '"]') : null) || document.querySelector('label[for="' + el.id + '"]'));
            if (hasLabel && !isHoneypotOrHidden(el)) {
                const tag = (el.tagName || '').toLowerCase();
                if (!['input', 'textarea', 'select', 'button', 'a', 'label'].includes(tag)) {
                    candidateInputs.push(el);
                }
            }
        }
    });

    // Deduplicate and consolidate outer hosts vs inner shadow inputs
    const finalInputs = candidateInputs.filter(el => {
        if (seenInputElements.has(el)) return false;
        const tag = (el.tagName || '').toLowerCase();
        if (tag !== 'input' && tag !== 'textarea') {
            const isDatePicker = el.classList.contains('datePicker') || (el.id && el.id.includes('datepicker')) || isCustomElement(el);
            if (!isDatePicker) {
                const innerInp = el.querySelector ? el.querySelector('input:not([type="hidden"]), textarea') : null;
                if (innerInp && seenInputElements.has(innerInp)) return false;
            }
        }
        seenInputElements.add(el);
        return true;
    });

    finalInputs.forEach(inp => {
        const lbl = getLabel(inp);
        if (!lbl) return;
        fldCount++;
        const localId = '@fld-' + fldCount;
        try { inp.setAttribute('data-wp-id', localId); } catch(e){}

        const tag = (inp.tagName || '').toLowerCase();
        const wc = (tag !== 'input' && tag !== 'textarea') ? (resolveWebComponent(inp) || inp) : null;
        const shadowInp = wc ? resolveShadowInput(inp) : null;
        if (wc) try { wc.setAttribute('data-wp-id', localId); } catch(e){}
        if (shadowInp) try { shadowInp.setAttribute('data-wp-id', localId); } catch(e){}

        const fmt = (wc && wc.getAttribute && (wc.getAttribute('format-pattern') || wc.getAttribute('placeholder'))) || inp.getAttribute('placeholder') || '';
        const isDatePicker = (
            inp.classList.contains('datePicker') || 
            (inp.id && inp.id.includes('datepicker')) || 
            (wc && (wc.tagName || '').toLowerCase().includes('date')) ||
            (wc && fmt && (fmt.toLowerCase().includes('dd/mm') || fmt.toLowerCase().includes('yyyy-mm'))) ||
            (inp.type === 'date')
        );
        const inpType = isDatePicker ? 'date' : (inp.type || (wc && wc.getAttribute('type')) || (inp.getAttribute('contenteditable') !== null ? 'contenteditable' : tag));

        let inpVal = (inp.value !== undefined && inp.value !== '') ? inp.value : '';
        if (!inpVal && wc) {
            inpVal = wc.value || (wc.getAttribute && wc.getAttribute('value')) || '';
        }
        if (!inpVal && shadowInp) {
            inpVal = shadowInp.value || '';
        }
        if (!inpVal && inp.isContentEditable) {
            inpVal = clean(inp.innerText || inp.textContent);
        }

        result.inputs.push({
            local_id: localId,
            id: inp.id || inp.name || (wc && (wc.id || wc.getAttribute('name'))) || '',
            label: lbl,
            type: inpType,
            required: isRequired(inp, lbl),
            value: inpVal
        });
    });

    // 6. Action Buttons
    const buttonEls = deepQueryAll(document, 'button, input[type="submit"], input[type="button"], a.btn, [role="button"], span[id$="_submitBtn"], span[id$="_saveBtn"]');
    const seenButtons = new Set();
    buttonEls.forEach(btn => {
        if (isHoneypotOrHidden(btn)) return;
        const id = btn.id || '';
        if (id.endsWith(':_selectButton')) return;
        const text = clean(btn.innerText || btn.value || btn.title);
        if (!text || text.length < 2 || text === 'Options' || text === 'Menu') return;

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

        btnCount++;
        const localId = '@btn-' + btnCount;
        try { btn.setAttribute('data-wp-id', localId); } catch(e){}

        result.buttons.push({
            local_id: localId,
            id: id,
            text: text,
            action: action
        });
    });

    return result;
"""

INSPECT_PAGE_DOM_SCRIPT: Final[str] = "(args = {}) => {\n" + UNIVERSAL_DOM_CORE_JS + "\n" + _INSPECT_LOGIC + "\n}"

PROBE_PICKLIST_OPTIONS_SCRIPT: Final[str] = """(ownsId) => {
    let container = ownsId ? document.getElementById(ownsId) : null;
    if (!container && !ownsId) container = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"])');
    if (!container) return [];
    const rawItems = Array.from(container.querySelectorAll('.globalMenuItem, a, li, [role="option"], [class*="selectItem"]'));
    const items = rawItems.filter(el => !rawItems.some(other => other !== el && el.contains(other)));
    return items.map(i => (i.getAttribute('title') || i.innerText || i.textContent || '').trim()).filter(t => t.length > 0 && !t.includes('Loading') && !t.includes('Press Up'));
}"""
