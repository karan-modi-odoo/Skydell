import publicWidget from "@web/legacy/js/public/public_widget";

const PHONE_COUNTRIES = [
    { name: "Afghanistan", dial: "+93", flag: "🇦🇫" },
    { name: "Albania", dial: "+355", flag: "🇦🇱" },
    { name: "Algeria", dial: "+213", flag: "🇩🇿" },
    { name: "Argentina", dial: "+54", flag: "🇦🇷" },
    { name: "Australia", dial: "+61", flag: "🇦🇺" },
    { name: "Austria", dial: "+43", flag: "🇦🇹" },
    { name: "Bangladesh", dial: "+880", flag: "🇧🇩" },
    { name: "Belgium", dial: "+32", flag: "🇧🇪" },
    { name: "Brazil", dial: "+55", flag: "🇧🇷" },
    { name: "Canada", dial: "+1", flag: "🇨🇦" },
    { name: "Chile", dial: "+56", flag: "🇨🇱" },
    { name: "China", dial: "+86", flag: "🇨🇳" },
    { name: "Colombia", dial: "+57", flag: "🇨🇴" },
    { name: "Czech Republic", dial: "+420", flag: "🇨🇿" },
    { name: "Denmark", dial: "+45", flag: "🇩🇰" },
    { name: "Egypt", dial: "+20", flag: "🇪🇬" },
    { name: "Finland", dial: "+358", flag: "🇫🇮" },
    { name: "France", dial: "+33", flag: "🇫🇷" },
    { name: "Germany", dial: "+49", flag: "🇩🇪" },
    { name: "Ghana", dial: "+233", flag: "🇬🇭" },
    { name: "Greece", dial: "+30", flag: "🇬🇷" },
    { name: "Hungary", dial: "+36", flag: "🇭🇺" },
    { name: "India", dial: "+91", flag: "🇮🇳" },
    { name: "Indonesia", dial: "+62", flag: "🇮🇩" },
    { name: "Iran", dial: "+98", flag: "🇮🇷" },
    { name: "Iraq", dial: "+964", flag: "🇮🇶" },
    { name: "Ireland", dial: "+353", flag: "🇮🇪" },
    { name: "Israel", dial: "+972", flag: "🇮🇱" },
    { name: "Italy", dial: "+39", flag: "🇮🇹" },
    { name: "Japan", dial: "+81", flag: "🇯🇵" },
    { name: "Jordan", dial: "+962", flag: "🇯🇴" },
    { name: "Kenya", dial: "+254", flag: "🇰🇪" },
    { name: "South Korea", dial: "+82", flag: "🇰🇷" },
    { name: "Kuwait", dial: "+965", flag: "🇰🇼" },
    { name: "Malaysia", dial: "+60", flag: "🇲🇾" },
    { name: "Mexico", dial: "+52", flag: "🇲🇽" },
    { name: "Morocco", dial: "+212", flag: "🇲🇦" },
    { name: "Nepal", dial: "+977", flag: "🇳🇵" },
    { name: "Netherlands", dial: "+31", flag: "🇳🇱" },
    { name: "New Zealand", dial: "+64", flag: "🇳🇿" },
    { name: "Nigeria", dial: "+234", flag: "🇳🇬" },
    { name: "Norway", dial: "+47", flag: "🇳🇴" },
    { name: "Pakistan", dial: "+92", flag: "🇵🇰" },
    { name: "Peru", dial: "+51", flag: "🇵🇪" },
    { name: "Philippines", dial: "+63", flag: "🇵🇭" },
    { name: "Poland", dial: "+48", flag: "🇵🇱" },
    { name: "Portugal", dial: "+351", flag: "🇵🇹" },
    { name: "Qatar", dial: "+974", flag: "🇶🇦" },
    { name: "Romania", dial: "+40", flag: "🇷🇴" },
    { name: "Russia", dial: "+7", flag: "🇷🇺" },
    { name: "Saudi Arabia", dial: "+966", flag: "🇸🇦" },
    { name: "Singapore", dial: "+65", flag: "🇸🇬" },
    { name: "South Africa", dial: "+27", flag: "🇿🇦" },
    { name: "Spain", dial: "+34", flag: "🇪🇸" },
    { name: "Sri Lanka", dial: "+94", flag: "🇱🇰" },
    { name: "Sweden", dial: "+46", flag: "🇸🇪" },
    { name: "Switzerland", dial: "+41", flag: "🇨🇭" },
    { name: "Taiwan", dial: "+886", flag: "🇹🇼" },
    { name: "Thailand", dial: "+66", flag: "🇹🇭" },
    { name: "Turkey", dial: "+90", flag: "🇹🇷" },
    { name: "UAE", dial: "+971", flag: "🇦🇪" },
    { name: "Uganda", dial: "+256", flag: "🇺🇬" },
    { name: "Ukraine", dial: "+380", flag: "🇺🇦" },
    { name: "United Kingdom", dial: "+44", flag: "🇬🇧" },
    { name: "United States", dial: "+1", flag: "🇺🇸" },
    { name: "Venezuela", dial: "+58", flag: "🇻🇪" },
    { name: "Vietnam", dial: "+84", flag: "🇻🇳" },
    { name: "Yemen", dial: "+967", flag: "🇾🇪" },
];

publicWidget.registry.PhonePicker = publicWidget.Widget.extend({
    selector: 'form[action="/submit-doctor-registration"]',
    events: {
        'click #phone_code_btn':     '_onToggleDropdown',
        'input #phone_code_search':  '_onPhoneSearch',
        'click .phone-country-item': '_onPhoneCountrySelect',
    },

    async start() {
        await this._super(...arguments);
        this._initPhonePicker();
        // Set USA as default
        this._setPhoneCountry({ name: "United States", dial: "+1", flag: "🇺🇸" });
    },

    _initPhonePicker() {
        // Render country list immediately
        this._renderPhoneList(PHONE_COUNTRIES);

        // Close dropdown when clicking outside
        document.addEventListener("click", (ev) => {
            const dropdown = this.el.querySelector("#country_code_dropdown");
            const btn      = this.el.querySelector("#phone_code_btn");
            if (!dropdown || !btn) return;
            if (!btn.contains(ev.target) && !dropdown.contains(ev.target)) {
                dropdown.style.display = "none";
            }
        });

        // Auto-sync dial code when Country of Practice changes
        const countrySelect = this.el.querySelector('select[name="country_id"]');
        if (countrySelect) {
            countrySelect.addEventListener("change", (ev) => {
                const selectedText = ev.currentTarget
                    .options[ev.currentTarget.selectedIndex]?.text?.trim();
                if (!selectedText) return;
                const match = PHONE_COUNTRIES.find(
                    (c) =>
                        selectedText.toLowerCase().includes(c.name.toLowerCase()) ||
                        c.name.toLowerCase().includes(selectedText.toLowerCase())
                );
                if (match) this._setPhoneCountry(match);
            });
        }
    },

    _renderPhoneList(countries) {
        const list = this.el.querySelector("#country_code_list");
        if (!list) return;

        if (countries.length === 0) {
            list.innerHTML = '<div class="p-3 text-muted small">No results found</div>';
            return;
        }

        list.innerHTML = countries.map((c) => `
            <div class="phone-country-item d-flex align-items-center gap-2 px-3 py-2"
                 style="cursor:pointer;"
                 data-dial="${c.dial}"
                 data-flag="${c.flag}"
                 data-name="${c.name}"
                 onmouseover="this.style.background='#f8f9fa'"
                 onmouseout="this.style.background='transparent'">
                <span style="font-size:1.1rem; min-width:24px;">${c.flag}</span>
                <span class="flex-grow-1 small">${c.name}</span>
                <span class="fw-bold text-primary small">${c.dial}</span>
            </div>
        `).join("");
    },

    _onToggleDropdown(ev) {
        ev.stopPropagation();
        const dropdown = this.el.querySelector("#country_code_dropdown");
        if (!dropdown) return;

        const isVisible = dropdown.style.display === "block";
        dropdown.style.display = isVisible ? "none" : "block";

        if (!isVisible) {
            setTimeout(() => {
                this.el.querySelector("#phone_code_search")?.focus();
            }, 50);
        }
    },

    _onPhoneSearch(ev) {
        const q = ev.currentTarget.value.toLowerCase().trim();
        const filtered = q
            ? PHONE_COUNTRIES.filter(
                (c) => c.name.toLowerCase().includes(q) || c.dial.includes(q)
              )
            : PHONE_COUNTRIES;
        this._renderPhoneList(filtered);
    },

    _onPhoneCountrySelect(ev) {
        ev.stopPropagation();
        const item = ev.currentTarget;
        this._setPhoneCountry({
            dial: item.dataset.dial,
            flag: item.dataset.flag,
            name: item.dataset.name,
        });

        // Close dropdown
        const dropdown = this.el.querySelector("#country_code_dropdown");
        if (dropdown) dropdown.style.display = "none";

        // Clear search & reset list
        const search = this.el.querySelector("#phone_code_search");
        if (search) {
            search.value = "";
            this._renderPhoneList(PHONE_COUNTRIES);
        }
    },

    _setPhoneCountry(country) {
        const flagEl     = this.el.querySelector("#selected_flag");
        const dialEl     = this.el.querySelector("#selected_dial_code");
        const hiddenCode = this.el.querySelector("#phone_country_code");
        if (flagEl)     flagEl.textContent = country.flag;
        if (dialEl)     dialEl.textContent = country.dial;
        if (hiddenCode) hiddenCode.value   = country.dial;
    },
});