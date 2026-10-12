"""Isolated DOM script for picklist auto-scrolling and option selection."""

from typing import Final

PICKLIST_AUTO_SCROLL_SCRIPT: Final[str] = """async ([inpId, target]) => {
    const input = inpId ? document.getElementById(inpId) : null;
    let list = null;
    if (input) {
        const owns = input.getAttribute('aria-owns');
        if (owns) list = document.getElementById(owns);
        if (!list && inpId.includes(':_input')) {
            const listId = inpId.replace(':_input', ':_listSelect');
            list = document.getElementById(listId);
        }
    }
    if (!list) {
        list = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"]), .globalMenu:not([style*="display: none"]), [class*="listSelect"]:not([style*="display: none"]), [id$=":_listSelect"]');
    }
    if (!list) {
        list = document;
    }

    let mode = 'smart';
    let rawTarget = String(target).trim();
    if (rawTarget.startsWith('@opt-')) { mode = 'index'; rawTarget = rawTarget.replace('@opt-', '').trim(); }
    else if (rawTarget.startsWith('text:')) { mode = 'text'; rawTarget = rawTarget.slice(5).trim(); }
    else if (rawTarget.startsWith('val:') || rawTarget.startsWith('value:')) { mode = 'value'; rawTarget = rawTarget.split(':', 2)[1].trim(); }
    else if (rawTarget.startsWith('id:')) { mode = 'id'; rawTarget = rawTarget.slice(3).trim(); }
    else if (rawTarget.startsWith('index:') || rawTarget.startsWith('#')) { mode = 'index'; rawTarget = rawTarget.replace(/^(index:|#)/, '').trim(); }
    else if (rawTarget.startsWith('re:') || rawTarget.startsWith('regex:')) { mode = 'regex'; rawTarget = rawTarget.split(':', 2)[1].trim(); }

    const targetLower = rawTarget.toLowerCase();
    let targetRegex = null;
    if (mode === 'regex') {
        try { targetRegex = new RegExp(rawTarget, 'i'); } catch(e){}
    }
    const targetIdx = mode === 'index' ? parseInt(rawTarget, 10) : null;
    const scrollParent = list !== document ? (list.closest('.scroll, .scrolling, div[style*="overflow"], div[style*="auto"]') || list.parentElement) : null;

    for (let scrollStep = 0; scrollStep < 25; scrollStep++) {
        const items = Array.from(list.querySelectorAll('a, li, [role="option"], .globalMenuItem, .picklistOption, [class*="selectListOption"], tr.dataRow, td[title]'));
        let match = null;

        if (mode === 'index') {
            if (targetIdx !== null && targetIdx > 0 && items.length >= targetIdx) {
                match = items[targetIdx - 1];
            }
        } else if (mode === 'value') {
            match = items.find(el => {
                const v = (el.value || el.getAttribute('data-value') || el.getAttribute('value') || '').trim().toLowerCase();
                return v === targetLower;
            });
        } else if (mode === 'id') {
            match = items.find(el => (el.id || '').toLowerCase() === targetLower);
        } else if (mode === 'regex' && targetRegex) {
            match = items.find(el => {
                const title = (el.getAttribute('title') || '').trim();
                const text = (el.innerText || el.textContent || '').trim();
                return targetRegex.test(title) || targetRegex.test(text);
            });
        } else if (mode === 'text') {
            match = items.find(el => {
                const title = (el.getAttribute('title') || '').trim().toLowerCase();
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                return title === targetLower || text === targetLower;
            });
        } else {
            // 'smart' mode: exact match first, then value/id, then substring
            match = items.find(el => {
                const title = (el.getAttribute('title') || '').trim().toLowerCase();
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                const val = (el.value || el.getAttribute('data-value') || el.getAttribute('value') || '').trim().toLowerCase();
                return title === targetLower || text === targetLower || val === targetLower || (el.id && el.id.toLowerCase() === targetLower);
            });
            if (!match) {
                match = items.find(el => {
                    const title = (el.getAttribute('title') || '').trim().toLowerCase();
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    return targetLower.length > 2 && (title.includes(targetLower) || text.includes(targetLower));
                });
            }
        }

        if (match) {
            try { match.dispatchEvent(new Event('mousedown', { bubbles: true })); } catch (e) {}
            match.click();
            try { match.dispatchEvent(new Event('mouseup', { bubbles: true })); } catch (e) {}
            return { success: true, text: match.getAttribute('title') || match.innerText || match.textContent };
        }

        if (scrollParent && scrollParent.scrollHeight > scrollParent.clientHeight) {
            const prevTop = scrollParent.scrollTop;
            scrollParent.scrollTop += 350;
            scrollParent.dispatchEvent(new Event('scroll', { bubbles: true }));
            if (scrollParent.scrollTop === prevTop) {
                break;
            }
            await new Promise(r => setTimeout(r, 80));
        } else {
            break;
        }
    }

    return { success: false, reason: 'not found' };
}"""

