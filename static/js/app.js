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
    
    // Auto-dismiss Django messages as toasts
    const messages = document.querySelectorAll('[data-toast]');
    messages.forEach(function(msg) {
        window.showToast(msg.textContent, msg.dataset.toast);
    });

    // Close modal on successful HTMX response
    document.body.addEventListener('htmx:beforeRequest', function(e) {
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

// Global function to close modal from HTMX responses
function closeModal() {
    window.dispatchEvent(new CustomEvent('close-modal'));
}
