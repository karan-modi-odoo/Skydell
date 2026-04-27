import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CountryCompliance = publicWidget.Widget.extend({
    selector: 'form[action="/submit-doctor-registration"]',

    events: {
        'change select[name="country_id"]': '_onCountryChange',
    },

    async start() {
        await this._super(...arguments);
        if (!document.getElementById("description")) return;
        await this._fetchCompliance(null);
    },

    async _onCountryChange(ev) {
        await this._fetchCompliance(ev.currentTarget.value || null);
    },

    async _fetchCompliance(countryId) {
        const complianceDesc  = document.getElementById("description");
        const complianceId    = document.getElementById("compliance_id");
        const complianceCheck = document.getElementById("compliance_accepted");

        if (!complianceDesc || !complianceId) return;

        try {
            const response = await fetch("/get-country-compliance", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method:  "call",
                    params:  { country_id: countryId ? parseInt(countryId) : null },
                }),
            });

            const { result } = await response.json();

            if (result && result.has_compliance) {
                complianceDesc.innerHTML = result.description || '';
                complianceId.value       = result.compliance_id || '';
                complianceCheck?.setAttribute('required', 'required');
                if (complianceCheck) complianceCheck.checked = false;
            } else {
                complianceDesc.innerHTML = '<p class="text-muted">No compliance available.</p>';
                complianceId.value       = '';
                complianceCheck?.removeAttribute('required');
                if (complianceCheck) complianceCheck.checked = false;
            }
        } catch (error) {
            console.error("Compliance fetch error:", error);
            complianceDesc.innerHTML = '<p class="text-danger">Failed to load compliance.</p>';
            complianceCheck?.removeAttribute('required');
        }
    },
});
