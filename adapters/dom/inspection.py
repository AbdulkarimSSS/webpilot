"""Isolated DOM scripts for page schema inspection and picklist option probing."""

from typing import Final

INSPECT_PAGE_DOM_SCRIPT: Final[str] = """(args = {}) => {
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
        if (!t) return '';
        let res = t;
        if (puaMode === 'strip') {
            res = res.replace(/[\uE000-\uF8FF]/g, '');
        } else if (puaMode === 'escape') {
            res = res.replace(/[\uE000-\uF8FF]/g, ch => '\\\\u' + ch.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0'));
        }
        return res.replace(/[\\u00a0\\r\\n\\t]+/g, ' ')
                .replace(/^[\\s\\*]+/, '')
                .trim();
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

    let fldCount = 0;
    let dropCount = 0;
    let optCount = 0;
    let upCount = 0;
    let btnCount = 0;

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

    const docLinks = Array.from(document.querySelectorAll('.documentName, a[href*="download"], a[title*="Download"], span[title*=".pdf"]'))
        .map(a => clean(a.innerText || a.title))
        .filter(t => t.includes('.pdf') || t.includes('.doc') || t.includes('.docx'));
    result.already_uploaded_files = Array.from(new Set(docLinks));

    // 3. Dropdowns & Picklists
    document.querySelectorAll('select').forEach(sel => {
        if (sel.offsetParent === null) return;
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
            optCount++;
            const localId = '@opt-' + optCount;
            choiceGroups[q] = {
                local_id: localId,
                id: r.id || r.name || q,
                name: r.name || r.id || q,
                label: q,
                question: q,
                type: (r.getAttribute('role') === 'radio' || r.type === 'radio') ? 'radio' : 'checkbox',
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
        fldCount++;
        const localId = '@fld-' + fldCount;
        try { inp.setAttribute('data-wp-id', localId); } catch(e){}

        result.inputs.push({
            local_id: localId,
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
}"""

PROBE_PICKLIST_OPTIONS_SCRIPT: Final[str] = """(ownsId) => {
    let container = ownsId ? document.getElementById(ownsId) : null;
    if (!container && !ownsId) container = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"])');
    if (!container) return [];
    const rawItems = Array.from(container.querySelectorAll('.globalMenuItem, a, li, [role="option"], [class*="selectItem"]'));
    const items = rawItems.filter(el => !rawItems.some(other => other !== el && el.contains(other)));
    return items.map(i => (i.getAttribute('title') || i.innerText || i.textContent || '').trim()).filter(t => t.length > 0 && !t.includes('Loading') && !t.includes('Press Up'));
}"""
