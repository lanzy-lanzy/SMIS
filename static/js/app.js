document.addEventListener('DOMContentLoaded', function() {
    // HTMX CSRF token configuration
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    document.body.addEventListener('htmx:configRequest', function(e) {
        e.detail.headers['X-CSRFToken'] = getCookie('csrftoken');
    });

    // Toast notification system
    window.showToast = function(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const accents = {
            success: 'toast-success',
            error: 'toast-error',
            warning: 'toast-warning',
            info: 'toast-info'
        };
        const icons = {
            success: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>',
            error: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>',
            warning: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>',
            info: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>'
        };
        const accent = accents[type] || accents.info;

        const toast = document.createElement('div');
        toast.className = 'toast ' + accent + ' translate-x-full opacity-0';
        toast.innerHTML = '<svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">' + (icons[type] || icons.info) + '</svg><span>' + message + '</span>';
        container.appendChild(toast);
        
        requestAnimationFrame(() => {
            toast.classList.remove('translate-x-full', 'opacity-0');
        });
        
        setTimeout(() => {
            toast.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };
    
    // Auto-dismiss Django messages as toasts (initial page load).
    document.querySelectorAll('[data-toast]').forEach(function (msg) {
        if (msg.dataset.toastShown === '1') return;
        msg.dataset.toastShown = '1';
        window.showToast(msg.textContent, msg.dataset.toast);
    });

    // Bridge HTMX swaps with Alpine.js and the toast system.
    //
    // When HTMX injects a partial (e.g. a modal form, a filtered table) any
    // Alpine component inside that fragment must be re-initialised -- Alpine's
    // own MutationObserver occasionally misses nodes replaced via `outerHTML`
    // swap or inserted with a click-outside/`x-cloak` still visible.
    // `Alpine.initializeTree` is idempotent, safe to call on already-hydrated
    // trees. Django [data-toast] markers injected via HTMX also need a
    // re-scan because the top-level loop above only runs once at boot.
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        const target = evt.detail && evt.detail.target;
        if (!target || !target.querySelectorAll) return;

        if (window.Alpine) {
            // Alpine v3 exposes `initTree` (some builds alias it as
            // `initializeTree`). Both are idempotent on already-hydrated nodes.
            const initFn = window.Alpine.initTree || window.Alpine.initializeTree;
            if (typeof initFn === 'function') {
                try { initFn.call(window.Alpine, target); } catch (_) { /* no-op */ }
            }
        }

        if (target.matches && target.matches('[data-toast]') && target.dataset.toastShown !== '1') {
            target.dataset.toastShown = '1';
            window.showToast(target.textContent, target.dataset.toast);
        }
        target.querySelectorAll('[data-toast]').forEach(function (msg) {
            if (msg.dataset.toastShown === '1') return;
            msg.dataset.toastShown = '1';
            window.showToast(msg.textContent, msg.dataset.toast);
        });
    });

    // Close modal on successful HTMX response
    document.body.addEventListener('htmx:beforeRequest', function (e) {
        const target = e.detail.target;
        if (target && target.id === 'modal-content') {
            // Show loading state
        }
    });
});

// Alpine.js modal component
function modal() {
    return {
        isOpen: false,
        loading: false,
        openModal(url) {
            this.isOpen = true;
            this.loading = true;
            const modalContent = document.getElementById('modal-content');
            modalContent.innerHTML = '<div class="p-6 text-center text-gray-500"><svg class="animate-spin h-8 w-8 mx-auto text-blue-500" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div>';
            htmx.ajax('GET', url, '#modal-content');
        },
        closeModal() {
            this.isOpen = false;
            this.loading = false;
            const modalContent = document.getElementById('modal-content');
            if (modalContent) modalContent.innerHTML = '';
        }
    };
}

// Transmutation of the initial (weighted) grade into the official term grade,
// mirroring grades/models.py. Bounds are integer hundredths so the comparison is
// exact at the 2-decimal precision the initial grade is stored with.
const TRANSMUTATION_BANDS = [
    [9950, 100], [9832, 99], [9714, 98], [9596, 97], [9478, 96], [9360, 95],
    [9242, 94], [9124, 93], [9006, 92], [8888, 91], [8770, 90], [8652, 89],
    [8534, 88], [8416, 87], [8298, 86], [8180, 85], [8062, 84], [7944, 83],
    [7826, 82], [7708, 81], [7590, 80], [7472, 79], [7354, 78], [7236, 77],
    [7118, 76], [7000, 75], [6534, 74], [6067, 73], [5601, 72], [5134, 71],
    [4667, 70], [4201, 69], [3734, 68], [3268, 67], [2801, 66], [2335, 65],
    [1868, 64], [1401, 63], [935, 62], [468, 61], [0, 60],
];

const DESCRIPTOR_BANDS = [
    [90, 'Advancing'], [80, 'Benchmarking'], [75, 'Connecting'],
    [65, 'Developing'], [0, 'Emerging'],
];

function transmuteGrade(initial) {
    const hundredths = Math.max(0, Math.min(10000, Math.round(Number(initial) * 100)));
    for (const [min, term] of TRANSMUTATION_BANDS) {
        if (hundredths >= min) return term;
    }
    return 60;
}

function gradeDescriptor(term) {
    for (const [min, name] of DESCRIPTOR_BANDS) {
        if (term >= min) return name;
    }
    return 'Emerging';
}

// Alpine.js grade-entry row component: dynamic item-count (scored/highest) badge,
// live percentage & weighted score per category, the live initial (weighted)
// grade, and the term grade it transmutes to with its descriptor. `init` is
// { w: { v: [v1..v5] }, p: { v: [v1..v3] }, a: { v: [v1..v3] }, savedInitial } seeded
// from the saved grade. The per-row numerator (raw total) is owned by the row; the
// denominator ("highest possible score") and the category weights (ww/pt/qa and
// wwMax/ptMax/qaMax, teacher-configured once on the <table> scope) resolve
// through the Alpine prototype-chain scope, so every row's badge reflects the
// class-wide maximum rather than a hardcoded 100.
function gradeRow(init) {
    init = init || {};
    function cat(seed) {
        seed = seed || {};
        const vals = Array.isArray(seed.v) ? seed.v : [];
        return {
            // Fixed 5 slots so array-index x-model bindings stay reactive; extra
            // slots render as empty inputs (performance/assessment use 1-3).
            v: [0, 1, 2, 3, 4].map(i => (vals[i] != null && vals[i] !== '' ? vals[i] : '')),
            get total() { return this.v.reduce((s, x) => s + (parseFloat(x) || 0), 0); },
        };
    }
    function saved(value) {
        const n = Number(value);
        // Rows created but never encoded store 0, which is not a grade: show "-"
        // instead of transmuting an empty row to the table's floor of 60.
        return n > 0 ? n : null;
    }
    return {
        _w: cat(init.w),
        _p: cat(init.p),
        _a: cat(init.a),
        _savedInitial: saved(init.savedInitial),
        fmt(n) {
            if (!isFinite(n)) return '0';
            return String(Math.round(n * 100) / 100);
        },
        // ww/pt/qa (weights) and wwMax/ptMax/qaMax (class maxima) come from the
        // parent <table> Alpine scope (merged via the prototype chain); these
        // getters read them with safe DepEd defaults (20 / 50 / 30).
        get _ww() { return (this.ww !== undefined ? this.ww : 20) || 0; },
        get _pt() { return (this.pt !== undefined ? this.pt : 50) || 0; },
        get _qa() { return (this.qa !== undefined ? this.qa : 30) || 0; },
        // Percentage score: raw total as a % of the class maximum (falls back to
        // treating the total as an already-percentage score when no max is set).
        ps(c, max) {
            const m = parseFloat(max);
            return (isFinite(m) && m > 0) ? c.total / m * 100 : c.total;
        },
        ws(c, weight, max) { return this.ps(c, max) * (weight || 0) / 100; },
        get liveQG() {
            const w = this._ww + this._pt + this._qa;
            if (w <= 0) return 0;
            return (this.ps(this._w, this.wwMax) * this._ww
                  + this.ps(this._p, this.ptMax) * this._pt
                  + this.ps(this._a, this.qaMax) * this._qa) / w;
        },
        // Initial grade: the weighted total at the 2-decimal precision it is stored
        // with, so the preview transmutes exactly like the server. Rows with nothing
        // entered fall back to their saved initial grade.
        get initialGrade() {
            const entered = (this._w.total + this._p.total + this._a.total) > 0;
            return entered ? Math.round(this.liveQG * 100) / 100 : this._savedInitial;
        },
        // Term grade: the initial grade run through the transmutation table.
        get termGrade() {
            return this.initialGrade === null ? null : transmuteGrade(this.initialGrade);
        },
        get description() {
            return this.termGrade === null ? '-' : gradeDescriptor(this.termGrade);
        },
    };
}

// Global function to close modal from HTMX responses
function closeModal() {
    window.dispatchEvent(new CustomEvent('close-modal'));
}

// ---------------------------------------------------------------------------
// Liquid glass sheen
// ---------------------------------------------------------------------------
// Glass surfaces carry a specular highlight. Tracking the pointer and feeding
// its position into the --mx / --my custom properties makes the highlight
// travel across the surface the way light behaves on real glass, which is
// what sells the material over a flat translucent panel.
//
// The pointer position is coalesced into a single animation frame so a fast
// mouse cannot flood the style engine, and the highlight is reset to its
// resting position when the pointer leaves the surface.
(function () {
    'use strict';

    var SHEEN_TARGETS = [
        '.glass', '.glass-panel', '.surface-card', '.stat-card',
        '.modal-card', '.toast', '.icon-tile',
        '.btn-secondary', '.formal-button-secondary'
    ].join(', ');

    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    var frame = null;
    var pending = null;
    var active = null;

    function reset(el) {
        if (!el) return;
        el.style.setProperty('--mx', '50%');
        el.style.setProperty('--my', '0%');
    }

    function paint() {
        frame = null;
        if (!pending) return;
        var el = pending.el;
        var rect = el.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        var x = ((pending.x - rect.left) / rect.width) * 100;
        var y = ((pending.y - rect.top) / rect.height) * 100;
        el.style.setProperty('--mx', x.toFixed(2) + '%');
        el.style.setProperty('--my', y.toFixed(2) + '%');
    }

    document.addEventListener('pointermove', function (e) {
        if (reduced.matches) return;
        var target = e.target;
        if (!target || typeof target.closest !== 'function') return;

        var el = target.closest(SHEEN_TARGETS);
        if (el !== active) {
            reset(active);
            active = el;
        }
        if (!el) return;

        pending = { el: el, x: e.clientX, y: e.clientY };
        if (frame === null) frame = requestAnimationFrame(paint);
    }, { passive: true });

    // Leaving the window should not strand a highlight mid-surface.
    window.addEventListener('pointerleave', function () {
        reset(active);
        active = null;
    });
})();
