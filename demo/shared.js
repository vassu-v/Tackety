/*
 * Shared helpers for the Tackety demo suite: API base, API-key storage,
 * an authenticated fetch wrapper, nav bar injection, and small UI utils.
 * Loaded by every page in /demo. Kept dependency-free on purpose - this
 * is a testing/demo UI meant to be readable, not a frontend build.
 */

const TACKETY_API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? 'http://localhost:8000'
    : window.location.origin;

const TK = {
    API_BASE: TACKETY_API_BASE,

    getApiKey() {
        return localStorage.getItem('tackety_api_key') || '';
    },

    setApiKey(key) {
        if (key) localStorage.setItem('tackety_api_key', key);
        else localStorage.removeItem('tackety_api_key');
    },

    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    },

    /** fetch() wrapper that attaches X-API-Key automatically. */
    async authFetch(path, options = {}) {
        const headers = Object.assign({}, options.headers || {}, {
            'X-API-Key': TK.getApiKey()
        });
        const res = await fetch(`${TK.API_BASE}${path}`, { ...options, headers });
        return res;
    },

    toast(message, kind = '') {
        let el = document.getElementById('tk-toast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'tk-toast';
            el.className = 'tk-toast';
            document.body.appendChild(el);
        }
        el.textContent = message;
        el.className = `tk-toast show ${kind}`;
        clearTimeout(el._hideTimer);
        el._hideTimer = setTimeout(() => el.classList.remove('show'), 3200);
    },

    /** Renders the shared top nav into #tk-nav-root, highlighting `active`. */
    renderNav(active) {
        const root = document.getElementById('tk-nav-root');
        if (!root) return;

        const links = [
            { href: 'index.html', label: 'Chat', id: 'chat' },
            { href: 'master.html', label: 'Overview', id: 'overview' },
            { href: 'queue.html', label: 'Developer Queue', id: 'queue' },
            { href: 'agent.html', label: 'Agent Workspace', id: 'agent' },
        ];

        const linkHtml = links.map(l =>
            `<a href="${l.href}" class="${l.id === active ? 'active' : ''}">${l.label}</a>`
        ).join('');

        root.innerHTML = `
            <div class="tk-nav">
                <div class="tk-nav-left">
                    <a href="master.html" class="tk-nav-logo">TACKETY</a>
                    <div class="tk-nav-links">${linkHtml}</div>
                </div>
                <div class="tk-nav-right">
                    <span class="tk-key-status" id="tk-key-status" title="API key status"></span>
                    <input type="password" class="tk-key-input" id="tk-key-input"
                        placeholder="X-API-Key (see server console)" autocomplete="off">
                </div>
            </div>
        `;

        const input = document.getElementById('tk-key-input');
        const status = document.getElementById('tk-key-status');
        input.value = TK.getApiKey();

        const refreshStatus = async () => {
            if (!input.value) { status.className = 'tk-key-status'; return; }
            try {
                const res = await fetch(`${TK.API_BASE}/support/queue`, {
                    headers: { 'X-API-Key': input.value }
                });
                status.className = 'tk-key-status' + (res.ok ? ' ok' : '');
            } catch (e) {
                status.className = 'tk-key-status';
            }
        };

        input.addEventListener('change', () => {
            TK.setApiKey(input.value);
            TK.toast('API key saved locally (this browser only).');
            refreshStatus();
            if (typeof window.onApiKeyChanged === 'function') window.onApiKeyChanged();
        });

        refreshStatus();
    }
};
