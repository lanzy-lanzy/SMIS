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
        
        const toast = document.createElement('div');
        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };
        toast.className = `${colors[type] || colors.info} text-white px-6 py-3 rounded-lg shadow-lg transform transition-all duration-300 translate-x-full opacity-0`;
        toast.innerHTML = `<div class="flex items-center gap-2"><span>${message}</span></div>`;
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

// Alpine.js grade-entry row component: dynamic item-count (scored/highest) badge,
// live percentage & weighted score per category, the live weighted quarter
// (initial) grade, and the DepEd letter description. `init` is
// { w: { v: [v1..v5] }, p: { v: [v1..v3] }, a: { v: [v1..v3] } } seeded from the
// saved grade. The per-row numerator (raw total) is owned by the row; the
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
    return {
        _w: cat(init.w),
        _p: cat(init.p),
        _a: cat(init.a),
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
        // Term grade = initial (weighted) grade rounded to nearest whole number.
        get termGrade() { return Math.round(this.liveQG); },
        // DepEd Order 8/2015 letter descriptor from the term grade.
        get description() {
            const g = this.termGrade;
            if (g >= 90) return 'A';
            if (g >= 85) return 'B';
            if (g >= 80) return 'C';
            if (g >= 75) return 'D';
            return 'E';
        },
    };
}

// Global function to close modal from HTMX responses
function closeModal() {
    window.dispatchEvent(new CustomEvent('close-modal'));
}
