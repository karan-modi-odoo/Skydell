/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";
import { markup } from "@odoo/owl";
import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Single unified compliance dialog — used for ALL scenarios:
 *   • Compliance description updated by admin
 *   • Country changed from the backend (doctor.registration form)
 *   • Country changed from the portal profile page (res.partner)
 *   • Company changed → compliance auto-updated
 *
 * When props.oldCountry / props.newCountry are present the country-change
 * banner is shown. The compliance description is always shown when available.
 */
class ComplianceReacceptDialog extends Component {
    static template = "adx_doctor_registration_portal.ComplianceReacceptDialog";
    static components = { Dialog };
    static props = {
        /** markup() Markup object — use 'true' to accept any type */
        description: true,
        /** Previous country name — present only when country changed */
        oldCountry: { type: String, optional: true },
        /** Current country name — present only when country changed */
        newCountry: { type: String, optional: true },
        close: { type: Function },
    };

    async onAccept() {
        try {
            const result = await rpc("/accept-regenerated-compliance", {});
            if (result && result.success) {
                this.props.close();
                // Reload so country, compliance_id and all UI state sync correctly
                window.location.reload();
            }
        } catch (error) {
            console.error("Error accepting compliance:", error);
        }
    }
}

/**
 * Public widget — runs on every portal page load for logged-in doctors.
 * Checks if compliance needs re-acceptance and shows the unified popup.
 */
publicWidget.registry.CompliancePopup = publicWidget.Widget.extend({
    selector: "#wrapwrap",

    init() {
        this._super(...arguments);
        this.dialog = this.bindService("dialog");
    },

    async start() {
        await this._super(...arguments);
        await this._checkComplianceAccepted();
    },

    async _checkComplianceAccepted() {
        try {
            const result = await rpc("/check-compliance-accepted", {});
            if (!result || !result.regenerated) return;

            // Build props for the single unified dialog
            const dialogProps = {
                // fields.Html returns raw HTML — wrap with markup() so OWL
                // t-out renders it as HTML instead of escaped text
                description: markup(result.description || ""),
            };

            // Include country props only when a country change was the trigger
            if (result.old_country && result.new_country) {
                dialogProps.oldCountry = result.old_country;
                dialogProps.newCountry = result.new_country;
            }

            this.dialog.add(ComplianceReacceptDialog, dialogProps);
        } catch (error) {
            console.error("Compliance check error:", error);
        }
    },
});
