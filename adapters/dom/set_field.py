"""Isolated DOM script for setting form field values."""

from typing import Final
from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS

_SET_FIELD_LOGIC: Final[str] = r"""
    let mode = 'contains';
    let rawTarget = (target || '').trim();
    if (rawTarget.startsWith('exact:')) { mode = 'exact'; rawTarget = rawTarget.slice(6).trim(); }
    else if (rawTarget.startsWith('re:') || rawTarget.startsWith('regex:')) { mode = 'regex'; rawTarget = rawTarget.slice(rawTarget.indexOf(':') + 1).trim(); }
    else if (rawTarget.startsWith('starts:') || rawTarget.startsWith('prefix:')) { mode = 'starts'; rawTarget = rawTarget.slice(rawTarget.indexOf(':') + 1).trim(); }
    else if (rawTarget.startsWith('ends:') || rawTarget.startsWith('suffix:')) { mode = 'ends'; rawTarget = rawTarget.slice(rawTarget.indexOf(':') + 1).trim(); }
    else if (rawTarget.startsWith('contains:')) { mode = 'contains'; rawTarget = rawTarget.slice(9).trim(); }

    const lowerTarget = rawTarget.toLowerCase();
    const hint = (typeHint || '').toLowerCase().trim();
    let targetRegex = null;
    if (mode === 'regex') {
        try { targetRegex = new RegExp(rawTarget, 'i'); } catch(e){}
    }


    function markActiveForm(node) {
        if (!node) return;
        try {
            let f = node.form || (node.closest ? node.closest('form') : null);
            if (!f && node.getRootNode) {
                const root = node.getRootNode();
                if (root && root.querySelector) {
                    f = root.querySelector('form');
                }
            }
            if (f && f.setAttribute) {
                f.setAttribute('data-wp-active-form', 'true');
            }
        } catch(e) {}
    }

    let parentScope = document;
    if (scopedParent && String(scopedParent).trim()) {
        const spLower = String(scopedParent).trim().toLowerCase();
        const containers = deepQueryAll(document, 'section, fieldset, details, tr, .rcmFormField, .rcmFormSection, .form-group, .accordion-item, div');
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
        if (el.getAttribute) {
            const ariaLbl = el.getAttribute('aria-label') || el.getAttribute('accessible-name') || el.getAttribute('title');
            if (ariaLbl && checkText(ariaLbl)) return true;
        }
        const wc = resolveWebComponent(el);
        if (wc && wc.getAttribute) {
            const wcLbl = wc.getAttribute('accessible-name') || wc.getAttribute('aria-label') || wc.getAttribute('title') || wc.getAttribute('placeholder');
            if (wcLbl && checkText(wcLbl)) return true;
        }

        if (el.id) {
            const root = el.getRootNode ? el.getRootNode() : document;
            try {
                const escId = (window.CSS && CSS.escape) ? CSS.escape(el.id) : el.id.replace(/(:|\.|\[|\]|,|=|@|"|\\)/g, "\\$1");
                const l = (root.querySelector ? root.querySelector('label[for="' + escId + '"]') : null) || document.querySelector('label[for="' + escId + '"]');
                if (l && l.innerText && checkText(l.innerText)) return true;
            } catch(e) {}
        }
        const parentLbl = el.closest ? el.closest('label') : null;
        if (parentLbl && parentLbl.innerText && checkText(parentLbl.innerText)) return true;
        if (el.previousElementSibling) {
            const prev = el.previousElementSibling;
            const pt = (prev.innerText || prev.textContent || '').trim();
            if (pt && pt.length < 60 && checkText(pt)) return true;
        }
        const container = el.closest ? el.closest('tr, .rcmFormField, .form-group, .field') : null;
        if (container && container !== el) {
            const header = container.querySelector('label, legend, .control-label, .field-label, th, dt, strong');
            if (header && header.innerText && checkText(header.innerText)) return true;
        }
        return false;
    }

    let exactEl = null;
    if (hint === 'selector' || hint === 'css' || hint === 'xpath' || rawTarget.startsWith('css=') || rawTarget.startsWith('css:') || rawTarget.startsWith('selector:') || rawTarget.startsWith('selector=') || rawTarget.startsWith('xpath=') || rawTarget.startsWith('xpath:') || rawTarget.startsWith('//')) {
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
    const NON_FIELD_TAGS = ['html', 'head', 'body', 'title', 'style', 'script', 'meta', 'link'];
    if (exactEl && NON_FIELD_TAGS.includes((exactEl.tagName || '').toLowerCase())) {
        exactEl = null;
    }

    // 1. SELECT
    if (!hint || hint === 'select' || hint === 'dropdown') {
        const selects = deepQueryAll(parentScope, 'select');
        const targetSelect = exactEl && exactEl.tagName === 'SELECT' ? exactEl : selects.find(s => !isHoneypotOrHidden(s) && matchElement(s));
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
                    targetSelect.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                    targetSelect.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
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
                targetSelect.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                targetSelect.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                return { success: matchedCount > 0, type: 'select', id: targetSelect.id, multiple: true };
            }

            let matched = false;
            // 1. Exact match on value or text
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
                } else if (valMode === 'smart' && (optVal === strVal || optText === strVal || (opt.text || '').trim().toLowerCase() === strVal)) {
                    targetSelect.value = opt.value;
                    matched = true;
                    break;
                }
            }

            // 2. Ranked Overlap Scoring for smart mode if exact match didn't find option
            if (!matched && valMode === 'smart' && strVal.length > 2) {
                // 2a. Phrase match
                const phraseMatches = Array.from(targetSelect.options).filter(opt => {
                    const optText = (opt.text || opt.innerText || '').toLowerCase();
                    return optText.includes(strVal);
                });
                if (phraseMatches.length > 0) {
                    phraseMatches.sort((a, b) => {
                        const lenA = (a.text || '').trim().length;
                        const lenB = (b.text || '').trim().length;
                        return Math.abs(lenA - strVal.length) - Math.abs(lenB - strVal.length);
                    });
                    targetSelect.value = phraseMatches[0].value;
                    matched = true;
                }

                // 2b. Strict Token Coverage match
                if (!matched) {
                    const targetTokens = strVal.split(/[\s,_\-\/]+/).filter(w => w.length > 1);
                    if (targetTokens.length > 1) {
                        let bestScore = 0;
                        let bestOpt = null;
                        for (let opt of targetSelect.options) {
                            const optText = (opt.text || opt.innerText || '').toLowerCase();
                            const optTokens = optText.split(/[\s,_\-\/]+/).filter(w => w.length > 1);
                            const matchedTokens = targetTokens.filter(t => optText.includes(t));
                            const coverage = matchedTokens.length / targetTokens.length;
                            if (coverage >= 0.8) {
                                const score = (2 * matchedTokens.length) / (targetTokens.length + optTokens.length);
                                if (score > bestScore) {
                                    bestScore = score;
                                    bestOpt = opt;
                                }
                            }
                        }
                        if (bestOpt) {
                            targetSelect.value = bestOpt.value;
                            matched = true;
                        }
                    }
                }
            }
            if (matched) {
                targetSelect.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                targetSelect.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                markActiveForm(targetSelect);
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

    // 2. Picklist / Combobox
    if (!hint || hint === 'picklist' || hint === 'combobox' || hint === 'dropdown') {
        const picklistInputs = deepQueryAll(parentScope, 'input, [role="combobox"], [aria-haspopup="listbox"]').filter(i => 
            (i.id && i.id.endsWith(':_input')) || i.getAttribute('role') === 'combobox' || (i.getAttribute('data-wp-id') && i.getAttribute('data-wp-id').startsWith('@drop-'))
        );
        const targetPicklist = (exactEl && picklistInputs.includes(exactEl)) ? exactEl : picklistInputs.find(p => !isHoneypotOrHidden(p) && matchElement(p));
        if (targetPicklist) {
            if (targetPicklist.disabled || targetPicklist.getAttribute('aria-disabled') === 'true') {
                return { success: false, type: 'picklist', id: targetPicklist.id, reason: 'Picklist is disabled (awaiting dependency)' };
            }
            const baseId = targetPicklist.id ? targetPicklist.id.replace(':_input', '') : '';
            const root = targetPicklist.getRootNode ? targetPicklist.getRootNode() : document;
            let btn = (baseId && root.getElementById ? root.getElementById(baseId + ':_selectButton') : null) || (baseId ? document.getElementById(baseId + ':_selectButton') : null);
            if (!btn) {
                btn = (targetPicklist.parentElement ? targetPicklist.parentElement.querySelector('button, [aria-haspopup="listbox"], .picklist-btn') : null)
                   || (targetPicklist.nextElementSibling && targetPicklist.nextElementSibling.tagName === 'BUTTON' ? targetPicklist.nextElementSibling : null);
            }
            if (!btn && targetPicklist.tagName && targetPicklist.tagName.toLowerCase() !== 'input') {
                btn = targetPicklist;
            }
            return { success: false, type: 'picklist', id: targetPicklist.id, trigger_button: btn ? btn.id : null };
        }
    }

    // 3. Radio / Checkboxes / Switches
    if (!hint || hint === 'choice' || hint === 'radio' || hint === 'checkbox' || hint === 'switch') {
        const choices = deepQueryAll(parentScope, 'input[type="radio"], input[type="checkbox"], [role="radio"], [role="checkbox"], [role="switch"]');
        const matchingChoices = choices.filter(c => !isHoneypotOrHidden(c) && (matchElement(c) || (c.name && c.name.toLowerCase().includes(lowerTarget))));
        if (matchingChoices.length > 0) {
            const strVal = String(val).toLowerCase();

            function getChoiceText(c) {
                let lbl = (c.value || '').toLowerCase();
                if (c.id) {
                    try {
                        const root = c.getRootNode ? c.getRootNode() : document;
                        const escId = (window.CSS && CSS.escape) ? CSS.escape(c.id) : c.id.replace(/(:|\.|\[|\]|,|=|@|"|\\)/g, "\\$1");
                        const l = (root.querySelector ? root.querySelector('label[for="' + escId + '"]') : null) || document.querySelector('label[for="' + escId + '"]');
                        if (l && (l.innerText || l.textContent)) {
                            lbl += ' ' + (l.innerText || l.textContent).toLowerCase();
                        }
                    } catch(e) {}
                }
                if (c.parentElement && c.parentElement.tagName === 'LABEL') {
                    lbl += ' ' + (c.parentElement.innerText || c.parentElement.textContent || '').toLowerCase();
                }
                if (c.nextElementSibling && ['LABEL', 'SPAN'].includes(c.nextElementSibling.tagName)) {
                    lbl += ' ' + (c.nextElementSibling.innerText || c.nextElementSibling.textContent || '').toLowerCase();
                } else if (c.nextSibling && c.nextSibling.textContent) {
                    lbl += ' ' + c.nextSibling.textContent.toLowerCase();
                }
                return lbl.trim();
            }

            // Handle [role="switch"]
            const sw = matchingChoices.find(c => c.getAttribute('role') === 'switch');
            if (sw) {
                const curOn = sw.getAttribute('aria-checked') === 'true';
                const wantOn = (val === true || strVal === 'on' || strVal === 'yes' || strVal === 'true' || strVal === '1');
                if (curOn !== wantOn) {
                    sw.click();
                }
                markActiveForm(sw);
                return { success: true, type: 'switch', id: sw.id || target, value: wantOn ? 'on' : '' };
            }

            // Handle multi-value checkbox group (e.g. "AI,Security")
            if (strVal.includes(',') && matchingChoices.some(c => c.type === 'checkbox' || c.getAttribute('role') === 'checkbox')) {
                const parts = strVal.split(',').map(s => s.trim().toLowerCase());
                let checkedCount = 0;
                for (let c of matchingChoices) {
                    const cVal = (c.value || '').toLowerCase();
                    const cLabel = getChoiceText(c);
                    if (parts.some(p => p && (cVal === p || cLabel.includes(p)))) {
                        c.checked = true;
                        c.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                        c.dispatchEvent(new Event('click', { bubbles: true, composed: true }));
                        checkedCount++;
                    }
                }
                if (checkedCount > 0) {
                    markActiveForm(matchingChoices[0]);
                    return { success: true, type: 'checkbox_group', id: matchingChoices[0].id || target, count: checkedCount };
                }
            }

            let chosen = null;
            // 1. Exact value match
            for (let c of matchingChoices) {
                if ((c.value && c.value.toLowerCase() === strVal) || (c.getAttribute && c.getAttribute('data-val') && c.getAttribute('data-val').toLowerCase() === strVal)) {
                    chosen = c;
                    break;
                }
            }
            // 2. Exact associated label match
            if (!chosen) {
                for (let c of matchingChoices) {
                    let directLabel = '';
                    if (c.id) {
                        try {
                            const root = c.getRootNode ? c.getRootNode() : document;
                            const escId = (window.CSS && CSS.escape) ? CSS.escape(c.id) : c.id.replace(/(:|\.|\[|\]|,|=|@|"|\\)/g, "\\$1");
                            const l = (root.querySelector ? root.querySelector('label[for="' + escId + '"]') : null) || document.querySelector('label[for="' + escId + '"]');
                            if (l && (l.innerText || l.textContent)) directLabel = (l.innerText || l.textContent).trim().toLowerCase();
                        } catch(e) {}
                    }
                    if (!directLabel && c.parentElement && c.parentElement.tagName === 'LABEL') {
                        directLabel = (c.parentElement.innerText || c.parentElement.textContent || '').trim().toLowerCase();
                    }
                    if (!directLabel && c.nextElementSibling && ['LABEL', 'SPAN'].includes(c.nextElementSibling.tagName)) {
                        directLabel = (c.nextElementSibling.innerText || c.nextElementSibling.textContent || '').trim().toLowerCase();
                    }
                    if (directLabel && directLabel === strVal) {
                        chosen = c;
                        break;
                    }
                }
            }
            // 3. Substring in choice text
            if (!chosen) {
                for (let c of matchingChoices) {
                    const cLabel = getChoiceText(c);
                    if (cLabel.includes(strVal)) {
                        chosen = c;
                        break;
                    }
                }
            }
            if (!chosen && matchingChoices.length === 1 && (val === true || strVal === 'yes' || strVal === 'true' || strVal === 'on')) {
                chosen = matchingChoices[0];
            }
            if (chosen) {
                if (chosen.tagName === 'INPUT') {
                    chosen.checked = true;
                    chosen.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                    chosen.dispatchEvent(new Event('click', { bubbles: true, composed: true }));
                } else {
                    chosen.click();
                }
                markActiveForm(chosen);
                return { success: true, type: chosen.getAttribute('role') || chosen.type || 'choice', id: chosen.id || '' };
            }
        }

        // Custom Radio Groups in containers
        const customGroups = deepQueryAll(parentScope, '[role="radiogroup"], .radioGroup, .rcmFormQuestionElement, .RCMFormField');
        const matchingGroup = customGroups.find(g => (g.innerText || '').toLowerCase().includes(lowerTarget));
        if (matchingGroup) {
            const strVal = String(val).toLowerCase();
            const radioOptions = Array.from(matchingGroup.querySelectorAll('.globalRadio, [role="radio"], .radioCheck, .sfRadioInputField, .radioLabel'));
            for (let opt of radioOptions) {
                const optText = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                const optVal = (opt.getAttribute('data-val') || '').toLowerCase();
                if (optText === strVal || optText.startsWith(strVal) || optVal === strVal) {
                    opt.click();
                    markActiveForm(opt);
                    return { success: true, type: 'custom_radio', id: opt.id || '', value: strVal };
                }
            }
        }
    }

    // 4. Text / Textarea / DatePicker / ContentEditable / Custom Web Components
    if (!hint || hint === 'text' || hint === 'input' || hint === 'textarea' || hint === 'string' || hint === 'number' || hint === 'date' || hint === 'datepicker' || hint === 'contenteditable') {
        const textCandidates = deepQueryAll(parentScope, 'input, textarea, [contenteditable="true"], [contenteditable=""], [contenteditable="plaintext-only"], [role="textbox"], [role="searchbox"], [role="spinbutton"], [role="slider"], *').filter(i => {
            const tag = (i.tagName || '').toLowerCase();
            if (tag === 'input' || tag === 'textarea') {
                const t = (i.type || '').toLowerCase();
                if (['radio', 'checkbox', 'file', 'hidden', 'submit', 'button', 'reset'].includes(t)) return false;
                if (i.id && i.id.endsWith(':_input') && hint !== 'text') return false;
                if (i.getAttribute('role') === 'combobox' && hint !== 'text') return false;
                return true;
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
            const primaryInputs = textCandidates.filter(i => {
                const tag = (i.tagName || '').toLowerCase();
                return tag === 'input' || tag === 'textarea' || i.isContentEditable || ['textbox', 'searchbox'].includes(i.getAttribute('role'));
            });
            targetText = primaryInputs.find(i => !isHoneypotOrHidden(i) && matchElement(i));
        }
        if (!targetText) {
            targetText = textCandidates.find(i => !isHoneypotOrHidden(i) && matchElement(i));
        }
        if (targetText) {
            const tag = (targetText.tagName || '').toLowerCase();
            const wc = (tag !== 'input' && tag !== 'textarea' && !targetText.isContentEditable) ? resolveWebComponent(targetText) : null;
            const shadowInp = wc ? resolveShadowInput(targetText) : null;

            if (targetText.disabled || targetText.getAttribute('aria-disabled') === 'true' ||
                (wc && (wc.disabled || wc.getAttribute('disabled') !== null || wc.getAttribute('aria-disabled') === 'true'))) {
                return { success: false, type: wc ? 'date' : tag, id: targetText.id, reason: 'Field is disabled (awaiting dependency)' };
            }

            let toSet = String(val);

            // Handle ContentEditable (Rich Text / Div Soup S41)
            if (targetText.isContentEditable || targetText.getAttribute('contenteditable') !== null) {
                targetText.focus();
                targetText.textContent = toSet;
                targetText.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, composed: true, inputType: 'insertText', data: toSet }));
                targetText.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: toSet }));
                targetText.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                targetText.dispatchEvent(new Event('blur', { bubbles: true, composed: true }));
                return { success: true, type: 'contenteditable', id: targetText.id || '', value: toSet };
            }

            // Handle ReadOnly input with Calendar Button fallback (S07)
            if (targetText.readOnly || (wc && (wc.readOnly || wc.getAttribute('readonly') !== null))) {
                const calButtons = deepQueryAll(document, '#cal button, .calendar button, [data-d], button[data-date]');
                const dateMatch = calButtons.find(b => {
                    const d = b.getAttribute('data-d') || b.getAttribute('data-date') || b.innerText.trim();
                    return d === toSet || toSet.endsWith(d);
                });
                if (dateMatch) {
                    dateMatch.click();
                    return { success: true, type: 'date', id: targetText.id, value: toSet };
                }
                return { success: false, type: wc ? 'date' : tag, id: targetText.id, reason: 'Field is read-only' };
            }

            // Date Normalization for Web Components and Date Inputs
            const fmtPattern = (wc && wc.getAttribute && (wc.getAttribute('format-pattern') || wc.getAttribute('placeholder'))) || targetText.getAttribute('placeholder') || '';
            const isDateField = tag === 'date' || targetText.type === 'date' || (fmtPattern && (fmtPattern.toLowerCase().includes('dd/mm') || fmtPattern.toLowerCase().includes('yyyy-mm'))) || (wc && (wc.tagName || '').toLowerCase().includes('date'));
            
            let isValidDate = true;
            if (isDateField && toSet) {
                const norm = normalizeUniversalDate(toSet, fmtPattern);
                toSet = norm.value;
                isValidDate = norm.isValid;
            }

            if (wc) {
                try { wc.value = toSet; } catch(e){}
                try { wc.setAttribute('value', toSet); } catch(e){}
                try { wc.setAttribute('value-state', isValidDate ? 'None' : 'Error'); } catch(e){}
                if (shadowInp) {
                    try {
                        const sProto = Object.getPrototypeOf(shadowInp);
                        const sDesc = Object.getOwnPropertyDescriptor(sProto, 'value');
                        if (sDesc && sDesc.set) sDesc.set.call(shadowInp, toSet);
                    } catch(e){}
                    try { shadowInp.value = toSet; } catch(e){}
                    shadowInp.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: toSet }));
                    shadowInp.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                    shadowInp.dispatchEvent(new Event('blur', { bubbles: true, composed: true }));
                }
                wc.dispatchEvent(new CustomEvent('input', { detail: { value: toSet, valid: isValidDate }, bubbles: true, composed: true }));
                wc.dispatchEvent(new CustomEvent('change', { detail: { value: toSet, valid: isValidDate }, bubbles: true, composed: true }));
                wc.dispatchEvent(new Event('blur', { bubbles: true, composed: true }));
                return { success: true, type: 'date', id: targetText.id || wc.id || '', value: toSet };
            }

            // Pre-focus element; if focusin detached and re-rendered the node (S48), catch the fresh node!
            try {
                targetText.focus();
                targetText.dispatchEvent(new FocusEvent('focusin', { bubbles: true, composed: true }));
                if (!document.contains(targetText)) {
                    const reFound = deepGetElementById(parentScope, targetText.id) || textCandidates.find(matchElement);
                    if (reFound) targetText = reFound;
                }
            } catch(e){}

            // Invoke native prototype descriptor setter for React / controlled synthetic state (S22, S33)
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

            targetText.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: toSet }));
            targetText.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
            targetText.dispatchEvent(new Event('blur', { bubbles: true, composed: true }));

            // Autocomplete / Typeahead suggestion matching (S03, S24)
            try {
                const sugContainers = deepQueryAll(document, '#sug, .sug, [role="listbox"]:not([style*="display: none"]), .cb-menu:not([style*="display: none"])');
                for (let sc of sugContainers) {
                    const items = Array.from(sc.querySelectorAll('div, [role="option"], li, a'));
                    const matchItem = items.find(it => (it.innerText || it.textContent || '').trim().toLowerCase() === toSet.toLowerCase());
                    if (matchItem) {
                        matchItem.click();
                        break;
                    }
                }
            } catch(e){}

            // Also sync companion hidden input if present in the same form (e.g. enterprise comboboxes / typeahead S24)
            try {
                const frm = (targetText.closest ? targetText.closest('form') : null) || targetText.form;
                if (frm) {
                    const hiddenInputs = Array.from(frm.querySelectorAll('input[type="hidden"]'));
                    let lblText = (targetText.labels && targetText.labels[0] ? targetText.labels[0].innerText : '') || '';
                    if (!lblText && targetText.id) {
                        try {
                            const esc = (window.CSS && CSS.escape) ? CSS.escape(targetText.id) : targetText.id;
                            const lEl = document.querySelector('label[for="' + esc + '"]');
                            if (lEl) lblText = lEl.innerText || lEl.textContent || '';
                        } catch(e) {}
                    }
                    const targetsToCheck = [lowerTarget, lblText.trim().toLowerCase()].filter(Boolean);
                    for (let h of hiddenInputs) {
                        const hName = (h.name || '').toLowerCase();
                        const hId = (h.id || '').toLowerCase();
                        const isMatch = targetsToCheck.some(t => hName === t || hId === t || (hName && t && (hName.includes(t) || t.includes(hName))));
                        if (isMatch) {
                            h.value = toSet;
                            h.dispatchEvent(new Event('input', { bubbles: true }));
                            h.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                }
            } catch(e){}

            markActiveForm(targetText);
            return { success: true, type: targetText.tagName.toLowerCase(), id: targetText.id, value: toSet };
        }
    }

    // Diagnostic probe for candidate elements that exist but were not interactable
    try {
        const allCandidates = deepQueryAll(document, 'input, select, textarea, [role="combobox"], [role="radiogroup"]');
        const cand = allCandidates.find(matchElement);
        if (cand) {
            if (isHoneypotOrHidden(cand)) {
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
"""

SET_FIELD_DOM_SCRIPT: Final[str] = "([target, val, typeHint, scopedParent]) => {\n" + UNIVERSAL_DOM_CORE_JS + "\n" + _SET_FIELD_LOGIC + "\n}"
