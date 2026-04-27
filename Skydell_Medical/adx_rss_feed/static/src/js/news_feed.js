/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.SkydellNewsFeed = publicWidget.Widget.extend({
    selector: ".skd-news-feed-page",

    async start() {
        await this._super(...arguments);
        this._initTheme();
        this._bindToggle();
    },

    _initTheme() {
        const saved = localStorage.getItem('skd-theme') || 'light';
        this._applyTheme(saved);
    },

    _bindToggle() {
        const btn = document.getElementById('skd-theme-toggle');
        if (!btn) return;
        btn.addEventListener('click', () => {
            const current = document.documentElement
                .getAttribute('data-skd-theme') || 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            this._applyTheme(next);
            localStorage.setItem('skd-theme', next);
        });
    },

    _applyTheme(theme) {
        document.documentElement.setAttribute('data-skd-theme', theme);
        const btn = document.getElementById('skd-theme-toggle');
        if (btn) {
            btn.textContent = theme === 'dark' ? '☀️' : '🌙';
            btn.title = theme === 'dark'
                ? 'Switch to light mode'
                : 'Switch to dark mode';
        }
    },
});
