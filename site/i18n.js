// ─── Shared i18n engine ──────────────────────────────────────────────────────
// Usage:
//   1. Add data-i18n="key" to any element whose textContent should be translated
//   2. Add data-i18n-html="key" for innerHTML translations
//   3. Call I18N.register({ key: "Korean text", ... }) per page
//   4. The nav toggle button is auto-injected

const I18N = (() => {
    const dict = {};
    let lang = localStorage.getItem('pm-lang') || 'en';

    // Common nav & shared UI translations
    const common = {
        'nav.home':         'PM 인텔',
        'nav.platform-war': '플랫폼 전쟁',
        'nav.arbitrage':    '차익거래 맵',
        'nav.wash-trading': '워시 트레이딩',
        'nav.election':     '선거 임팩트',
        'nav.concentration':'집중도 분석',
        'nav.timelapse':    '타임랩스',
    };

    function register(pageDict) {
        Object.assign(dict, common, pageDict);
    }

    function apply() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (lang === 'ko' && dict[key]) {
                if (!el._origText) el._origText = el.textContent;
                el.textContent = dict[key];
            } else if (lang === 'en' && el._origText) {
                el.textContent = el._origText;
            }
        });
        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const key = el.getAttribute('data-i18n-html');
            if (lang === 'ko' && dict[key]) {
                if (!el._origHTML) el._origHTML = el.innerHTML;
                el.innerHTML = dict[key];
            } else if (lang === 'en' && el._origHTML) {
                el.innerHTML = el._origHTML;
            }
        });
        // Update button label
        const btn = document.getElementById('langToggle');
        if (btn) btn.textContent = lang === 'en' ? '한국어' : 'English';
    }

    function toggle() {
        lang = lang === 'en' ? 'ko' : 'en';
        localStorage.setItem('pm-lang', lang);
        apply();
    }

    function injectButton() {
        const nav = document.querySelector('nav .max-w-7xl');
        if (!nav) return;
        const btn = document.createElement('button');
        btn.id = 'langToggle';
        btn.className = 'ml-auto text-xs px-3 py-1.5 rounded-lg bg-dark-700 text-gray-300 hover:text-white border border-gray-600/50 transition whitespace-nowrap shrink-0';
        btn.textContent = lang === 'en' ? '한국어' : 'English';
        btn.addEventListener('click', toggle);
        nav.appendChild(btn);
    }

    function init(pageDict) {
        register(pageDict || {});
        injectButton();
        if (lang === 'ko') apply();
    }

    return { init, apply, toggle, lang: () => lang };
})();
