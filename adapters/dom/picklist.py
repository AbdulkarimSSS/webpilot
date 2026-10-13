"""Isolated DOM script for picklist auto-scrolling and option selection."""

from typing import Final

PICKLIST_AUTO_SCROLL_SCRIPT: Final[str] = """async ([inpId, target]) => {
    const input = inpId ? document.getElementById(inpId) : null;
    let list = null;
    const owns = input ? (input.getAttribute('aria-owns') || input.getAttribute('aria-controls')) : null;
    if (owns) {
        list = document.getElementById(owns);
    }
    if (!list && input && inpId.includes(':_input')) {
        const listId = inpId.replace(':_input', ':_listSelect');
        list = document.getElementById(listId);
    }
    // Only fallback to generic listbox if input did NOT explicitly define aria-owns
    if (!list && input && !owns) {
        list = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"]), .globalMenu:not([style*="display: none"]), [class*="listSelect"]:not([style*="display: none"])');
    }
    if (!list && !input) {
        list = document.querySelector('[role="listbox"]:not([style*="display: none"]), .rcmpaginatedselectlist:not([style*="display: none"]), .globalMenu:not([style*="display: none"])') || document;
    }
    if (!list) {
        return { success: false, reason: 'list_not_ready' };
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
    const scrollParent = list !== document
        ? (list.closest('.globalMenu, .sf-combo-listselect, [onscroll], .scroll, .scrolling, div[style*="overflow"], div[style*="auto"]')
           || (list.scrollHeight > list.clientHeight ? list : list.parentElement))
        : null;
    const searchRoot = (scrollParent && scrollParent.contains(list)) ? scrollParent : list;
    const isPaginatedMenu = !!(scrollParent && (scrollParent.classList.contains('sf-combo-listselect') || scrollParent.querySelector('.scrolling-page, .fetch-page-in-order')));

    for (let scrollStep = 0; scrollStep < 35; scrollStep++) {
        const rawItems = Array.from(searchRoot.querySelectorAll('a, li, [role="option"], [role="menuitem"], .globalMenuItem, .picklistOption, .rcmpaginatedselectitem, [class*="selectListOption"], [class*="selectItem"], tr.dataRow, td[title]'));
        // Deduplicate wrapper elements (e.g. keep inner <a> if wrapped by <li>)
        const items = rawItems.filter(el => !rawItems.some(other => other !== el && el.contains(other)))
                              .filter(el => {
                                  const t = (el.innerText || el.textContent || '').trim();
                                  return t.length > 0 && !t.includes('Loading') && !t.includes('Press Up');
                              });

        if (items.length === 0) {
            return { success: false, reason: 'list_not_ready' };
        }

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
            // 'smart' mode: multi-tier ranked scoring to eliminate false greedy collisions (e.g. Electrical vs Aeronautical Engineering)
            // Priority 1: Exact match on title, text, value, or id
            match = items.find(el => {
                const title = (el.getAttribute('title') || '').trim().toLowerCase();
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                const val = (el.value || el.getAttribute('data-value') || el.getAttribute('value') || '').trim().toLowerCase();
                return title === targetLower || text === targetLower || val === targetLower || (el.id && el.id.toLowerCase() === targetLower);
            });

            // Priority 2: Full continuous phrase match (target is unbroken substring)
            if (!match && targetLower.length > 2) {
                // Collect candidates where unbroken phrase is contained
                const phraseCandidates = items.filter(el => {
                    const title = (el.getAttribute('title') || '').trim().toLowerCase();
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    return title.includes(targetLower) || text.includes(targetLower);
                });
                if (phraseCandidates.length > 0) {
                    // Pick the candidate whose length is closest to targetLower (best compactness)
                    phraseCandidates.sort((a, b) => {
                        const lenA = ((a.getAttribute('title') || '') || (a.innerText || '')).trim().length;
                        const lenB = ((b.getAttribute('title') || '') || (b.innerText || '')).trim().length;
                        return Math.abs(lenA - targetLower.length) - Math.abs(lenB - targetLower.length);
                    });
                    match = phraseCandidates[0];
                }
            }

            // Priority 3: Ranked Token-Coverage Scoring (Strict All-Tokens Containment)
            if (!match && targetLower.length > 2) {
                const targetTokens = targetLower.split(/[\s,_\-\/]+/).filter(w => w.length > 1);
                if (targetTokens.length > 1) {
                    let bestScore = 0;
                    let bestEl = null;

                    for (const el of items) {
                        const optText = ((el.getAttribute('title') || '') + ' ' + (el.innerText || el.textContent || '')).toLowerCase();
                        const optTokens = optText.split(/[\s,_\-\/]+/).filter(w => w.length > 1);

                        // How many target tokens are present in this option?
                        const matchedTokens = targetTokens.filter(t => optText.includes(t));
                        const coverage = matchedTokens.length / targetTokens.length;

                        // Reject if coverage < 0.8 (e.g. 'electrical' missing -> coverage 0.5 -> rejected!)
                        if (coverage >= 0.8) {
                            const score = (2 * matchedTokens.length) / (targetTokens.length + optTokens.length);
                            if (score > bestScore) {
                                bestScore = score;
                                bestEl = el;
                            }
                        }
                    }
                    if (bestEl) {
                        match = bestEl;
                    }
                }
            }
        }

        if (match) {
            try {
                document.querySelectorAll('[data-wp-pick-target]').forEach(el => el.removeAttribute('data-wp-pick-target'));
                match.setAttribute('data-wp-pick-target', '1');
                if (match.scrollIntoView) match.scrollIntoView({ block: 'nearest' });
            } catch (e) {}
            try { match.focus(); } catch (e) {}
            try { match.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window })); } catch (e) {}
            match.click();
            try { match.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window })); } catch (e) {}
            return { success: true, text: (match.getAttribute('title') || match.innerText || match.textContent || '').trim() };
        }

        if (scrollParent && scrollParent.scrollHeight > scrollParent.clientHeight) {
            const prevTop = scrollParent.scrollTop;
            const prevSh = scrollParent.scrollHeight;
            const prevCount = items.length;
            if (isPaginatedMenu) {
                scrollParent.scrollTop = scrollParent.scrollHeight;
            } else {
                scrollParent.scrollTop += 350;
            }
            scrollParent.dispatchEvent(new Event('scroll', { bubbles: true }));
            if (scrollParent.scrollTop === prevTop || isPaginatedMenu) {
                // Wait up to 900ms for AJAX pagination to append new items or increase scrollHeight
                let loadedMore = false;
                for (let w = 0; w < 9; w++) {
                    await new Promise(r => setTimeout(r, 100));
                    const curCount = searchRoot.querySelectorAll('li, [role="option"], .globalMenuItem, .picklistOption').length;
                    if (scrollParent.scrollHeight > prevSh || curCount > prevCount) {
                        loadedMore = true;
                        break;
                    }
                }
                if (!loadedMore && scrollParent.scrollTop === prevTop) {
                    break;
                }
            } else {
                await new Promise(r => setTimeout(r, 80));
            }
        } else {
            break;
        }
    }

    return { success: false, reason: 'not_found' };
}"""

