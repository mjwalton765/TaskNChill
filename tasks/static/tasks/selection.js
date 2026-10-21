function updateSelection(form) {
    const boxes = form.querySelectorAll('input[name="selected"]');
    let count = 0;
    for (const box of boxes) {
        if (box.checked) {
            count += 1;
        }
    }
    const all = form.querySelector('[data-select-all]');
    if (all) {
        all.checked = count > 0 && count === boxes.length;
        all.indeterminate = count > 0 && count < boxes.length;
    }
    const counter = form.querySelector('[data-selection-count]');
    if (counter) {
        counter.textContent = `${count} selected`;
    }
    for (const button of form.querySelectorAll('[data-needs-selection]')) {
        button.disabled = count === 0;
    }
    for (const button of form.querySelectorAll('[data-single-selection]')) {
        button.disabled = count !== 1;
    }
}

function initializeDates() {
    const formatter = new Intl.DateTimeFormat(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
    });
    for (const element of document.querySelectorAll('time[data-local-time]')) {
        const date = new Date(element.dateTime);
        if (!Number.isNaN(date.getTime())) {
            element.textContent = formatter.format(date);
        }
    }
}

function initializeSelection() {
    initializeDates();
    for (const form of document.querySelectorAll('.selection-form')) {
        updateSelection(form);
    }
}

document.addEventListener('change', event => {
    const form = event.target.closest('.selection-form');
    if (!form) {
        return;
    }
    if (event.target.matches('[data-select-all]')) {
        for (const box of form.querySelectorAll('input[name="selected"]')) {
            box.checked = event.target.checked;
        }
    }
    updateSelection(form);
});
initializeSelection();

const positionKey = 'tasknchill-action-position';
const results = document.getElementById('task-results');

function savePosition(restoreScroll) {
    if (!results) return;
    const boxes = [...results.querySelectorAll('input[name="selected"]')];
    const visible = boxes.find(box => box.closest('li').getBoundingClientRect().bottom > 0);
    const state = {
        url: results.dataset.listUrl,
        time: Date.now(),
        y: restoreScroll ? window.scrollY : null,
        anchor: visible ? visible.value : null,
        offset: visible ? visible.closest('li').getBoundingClientRect().top : 0,
        selected: boxes.filter(box => box.checked).map(box => box.value),
        expanded: boxes.filter(box => box.closest('li').querySelector('details[open]')).map(box => box.value),
    };
    try {
        sessionStorage.setItem(positionKey, JSON.stringify(state));
    } catch (error) {}
}

document.addEventListener('submit', event => {
    if (event.target.matches('.selection-form')) savePosition(true);
});

document.addEventListener('click', event => {
    if (event.target.closest('a[data-sort], a[data-list-page]') &&
        event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
        savePosition(false);
    }
});

function restorePosition() {
    if (!results) return;
    try {
        const state = JSON.parse(sessionStorage.getItem(positionKey));
        sessionStorage.removeItem(positionKey);
        if (!state || Date.now() - state.time > 1800000) return;
        const origin = new URL(state.url, window.location.origin);
        if (origin.pathname !== window.location.pathname) return;
        const current = new URL(window.location.href);
        origin.searchParams.delete('page');
        current.searchParams.delete('page');
        if (state.y !== null && origin.search !== current.search) return;
        let anchor;
        for (const box of results.querySelectorAll('input[name="selected"]')) {
            box.checked = state.selected.includes(box.value);
            const row = box.closest('li');
            const details = row.querySelector('details');
            if (details) details.open = state.expanded.includes(box.value);
            if (box.value === state.anchor) anchor = row;
        }
        initializeSelection();
        if (state.y !== null) {
            requestAnimationFrame(() => {
                const top = anchor ? window.scrollY + anchor.getBoundingClientRect().top - state.offset : state.y;
                window.scrollTo({top: Math.max(0, top), behavior: 'instant'});
            });
        }
    } catch (error) {}
}

if (document.readyState === 'complete') restorePosition();
else window.addEventListener('load', restorePosition, {once: true});
setTimeout(() => {
    for (const notice of document.querySelectorAll('[data-message-level="success"]')) notice.remove();
}, 3000);
