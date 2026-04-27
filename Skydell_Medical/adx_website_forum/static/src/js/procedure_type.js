/** @odoo-module **/
/**
 * procedure_type.js
 * =================
 * Handles all interactivity for the Procedure & Product Details section
 * on both the NEW POST and EDIT POST forum pages.
 *
 * Responsibilities:
 *  1. Toggle show/hide of the entire procedure card.
 *  2. Auto-fill Procedure Description when a type is selected.
 *  3. Show/hide the "Other Procedure" row when "Other" is selected.
 *  4. Set/unset HTML required attribute on mandatory fields.
 *  5. Validate required fields on form submit and show inline errors.
 *  6. Live-clear error states as the doctor fills in fields.
 *
 * No changes to core logic from previous version.
 * Selector updated: description field resolved via textarea id
 * (before Odoo WYSIWYG initialises) or .odoo-editor-editable
 * (after WYSIWYG initialises) — both are checked.
 */

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ForumProcedureSection = publicWidget.Widget.extend({
    selector: 'form.js_website_submit_form',

    start() {
        this._super(...arguments);
        // Track whether the user has clicked submit at least once.
        // Before first submit, live-validation errors are never shown.
        this._submitAttempted = false;
        // Set of field IDs the user has interacted with (touched)
        this._touched = new Set();
        this._initToggle();
        this._initProcedureTypeChange();
        this._initValidation();
        this._initLiveClear();
        this._initTouchedTracking();
    },

    // ── 1. Toggle show / hide whole section ───────────────────────
    _initToggle() {
        const cb  = document.getElementById('is_procedure_post');
        const sec = document.getElementById('skd-procedure-section');
        if (!cb || !sec) return;

        this._applyToggle(cb, sec);
        cb.addEventListener('change', () => this._applyToggle(cb, sec));
    },

    _applyToggle(cb, sec) {
        if (cb.checked) {
            sec.classList.remove('d-none');
            this._setRequired(true);
            const sel = document.getElementById('procedure_type_id');
            if (sel) {
                this._applyOtherRow(sel);
                this._autofillDescription(sel, /*onLoad=*/true);
            }
        } else {
            sec.classList.add('d-none');
            this._setRequired(false);
            this._hideOtherRow();
            this._clearErrors();
        }
    },

    // ── 2 & 3. Handle Procedure Type dropdown change ──────────────
    _initProcedureTypeChange() {
        const sel = document.getElementById('procedure_type_id');
        if (!sel) return;

        // Run on page load — handles pre-selected value on edit page
        this._applyOtherRow(sel);
        this._autofillDescription(sel, /*onLoad=*/true);

        sel.addEventListener('change', () => {
            this._applyOtherRow(sel);
            this._autofillDescription(sel, /*onLoad=*/false);
        });
    },

    // Show/hide Other row based on data-is-other attribute
    _applyOtherRow(sel) {
        const opt      = sel.options[sel.selectedIndex];
        const isOther  = opt && opt.getAttribute('data-is-other') === '1';
        const otherRow = document.getElementById('skd-other-procedure-row');
        if (!otherRow) return;

        if (isOther) {
            otherRow.classList.remove('d-none');
            const inp = document.getElementById('other_procedure_detail');
            const sec = document.getElementById('skd-procedure-section');
            const sectionActive = sec && !sec.classList.contains('d-none');
            if (inp) {
                if (sectionActive) inp.setAttribute('required', 'required');
                else inp.removeAttribute('required');
            }
            // Dropdown itself is no longer required — Other field takes over
            const pt = document.getElementById('procedure_type_id');
            if (pt) pt.removeAttribute('required');
        } else {
            this._hideOtherRow();
        }
    },

    _hideOtherRow() {
        const otherRow = document.getElementById('skd-other-procedure-row');
        if (!otherRow) return;
        otherRow.classList.add('d-none');
        const inp = document.getElementById('other_procedure_detail');
        if (inp) {
            inp.removeAttribute('required');
            inp.value = '';
            inp.classList.remove('is-invalid', 'is-valid');
        }
        // Restore required to the dropdown when Other row is hidden
        const sec = document.getElementById('skd-procedure-section');
        const sectionActive = sec && !sec.classList.contains('d-none');
        const pt = document.getElementById('procedure_type_id');
        if (pt) {
            if (sectionActive) pt.setAttribute('required', 'required');
            else pt.removeAttribute('required');
        }
        const otherDesc = document.getElementById('other_procedure_description');
        if (otherDesc) {
            // Clear both raw textarea and WYSIWYG editable if initialised
            otherDesc.value = '';
            const editor = otherDesc.closest('.o_wysiwyg_textarea_wrapper');
            if (editor) {
                const editable = editor.querySelector('.odoo-editor-editable');
                if (editable) editable.innerHTML = '';
            }
        }
        this._hideErr('err_other_detail');
    },

    // Auto-fill Procedure Description textarea from data-description
    _autofillDescription(sel, onLoad) {
        const wrapper = document.getElementById('procedure_description_wrapper');
        if (!wrapper) return;

        // Prefer the live WYSIWYG editable; fall back to raw textarea
        const descEl = wrapper.querySelector('.odoo-editor-editable')
                    || wrapper.querySelector('#procedure_description');
        if (!descEl) return;

        const opt = sel.options[sel.selectedIndex];
        if (!opt || !opt.value) {
            if (!onLoad) {
                if (descEl.tagName === 'TEXTAREA') descEl.value = '';
                else descEl.innerHTML = '';
                wrapper.classList.remove('d-none');
            }
            return;
        }

        const isOther = opt.getAttribute('data-is-other') === '1';
        if (isOther) {
            // Hide Procedure Summary row entirely when "Other" is selected
            if (descEl.tagName === 'TEXTAREA') descEl.value = '';
            else descEl.innerHTML = '';
            wrapper.classList.add('d-none');
            // Remove required so browser native validation doesn't block submit
            const psEl = document.getElementById('procedure_description');
            if (psEl) psEl.removeAttribute('required');
            return;
        }
        // Restore required only if the procedure section is currently active
        const sec = document.getElementById('skd-procedure-section');
        const sectionActive = sec && !sec.classList.contains('d-none');
        const psEl = document.getElementById('procedure_description');
        if (psEl && sectionActive) psEl.setAttribute('required', 'required');
        else if (psEl) psEl.removeAttribute('required');

        // Normal procedure type — ensure summary row is visible
        wrapper.classList.remove('d-none');

        const dataDesc = (opt.getAttribute('data-description') || '').trim();

        if (onLoad) {
            // Only fill when currently empty (don't overwrite saved content)
            const currentVal = descEl.tagName === 'TEXTAREA'
                ? descEl.value.trim()
                : descEl.innerHTML.trim();
            if (!currentVal) {
                if (descEl.tagName === 'TEXTAREA') descEl.value = dataDesc;
                else descEl.innerHTML = dataDesc;
            }
        } else {
            // Manual change — always update
            if (descEl.tagName === 'TEXTAREA') descEl.value = dataDesc;
            else descEl.innerHTML = dataDesc;
        }
    },

    // ── 4. Set / unset required on ALL procedure fields ────────────
    _setRequired(on) {
        [
            'procedure_type_id', 'procedure_description', 'product_used_id',
            'duration', 'duration_unit', 'date_performed',
            'recovery_period_value', 'recovery_period_unit',
            'recovery', 'risk_level', 'risks', 'results',
        ].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            on ? el.setAttribute('required', 'required')
               : el.removeAttribute('required');
        });
    },

    // ── 5. Form submit validation ─────────────────────────────────
    _initValidation() {
        const form = document.querySelector('form.js_website_submit_form');
        if (!form) return;

        form.addEventListener('submit', ev => {
            const cb = document.getElementById('is_procedure_post');
            if (!cb || !cb.checked) return;

            // Mark that submit has been attempted — live validation activates
            this._submitAttempted = true;

            let hasError = false;

            // Procedure Type — skip if Other row is visible (other_procedure_detail takes over)
            const otherRowVisible = (() => {
                const r = document.getElementById('skd-other-procedure-row');
                return r && !r.classList.contains('d-none');
            })();
            const pt = document.getElementById('procedure_type_id');
            if (!otherRowVisible) {
                if (pt && !pt.value) {
                    this._showErr('err_procedure_type');
                    this._invalid(pt);
                    hasError = true;
                } else {
                    this._hideErr('err_procedure_type');
                    if (pt) this._valid(pt);
                }
            } else {
                this._hideErr('err_procedure_type');
                if (pt) this._valid(pt);
            }

            // Other detail (only when Other row is visible)
            const otherRow = document.getElementById('skd-other-procedure-row');
            if (otherRow && !otherRow.classList.contains('d-none')) {
                const oi = document.getElementById('other_procedure_detail');
                if (oi && !oi.value.trim()) {
                    this._showErr('err_other_detail');
                    this._invalid(oi);
                    hasError = true;
                } else {
                    this._hideErr('err_other_detail');
                    if (oi) this._valid(oi);
                }
            }

            // Procedure Summary — skip when "Other" is selected (wrapper is hidden)
            const psWrapper = document.getElementById('procedure_description_wrapper');
            const ps = document.getElementById('procedure_description');
            if (ps && psWrapper && !psWrapper.classList.contains('d-none')) {
                if (!ps.value.trim()) {
                    this._invalid(ps);
                    hasError = true;
                }
            }

            // Duration
            const du = document.getElementById('duration');
            if (du && !du.value) {
                this._invalid(du);
                hasError = true;
            }
            // Duration unit
            const dunit = document.getElementById('duration_unit');
            if (dunit && !dunit.value) {
                this._invalid(dunit);
                hasError = true;
            }

            // Recovery Period
            const rp = document.getElementById('recovery_period_value');
            if (rp && !rp.value) {
                this._invalid(rp);
                hasError = true;
            }

            // Recovery Period unit
            const rpu = document.getElementById('recovery_period_unit');
            if (rpu && !rpu.value) {
                this._invalid(rpu);
                hasError = true;
            }

            // Recovery Notes (WYSIWYG)
            if (!this._wysiwyg_has_content('#recovery_wrapper', 'recovery')) {
                this._invalidWysiwyg('#recovery_wrapper', 'err_recovery');
                hasError = true;
            } else {
                this._validWysiwyg('#recovery_wrapper', 'err_recovery');
            }

            // Risk Level
            const rl = document.getElementById('risk_level');
            if (rl && !rl.value) {
                this._invalid(rl);
                hasError = true;
            }

            // Risk Details (WYSIWYG)
            if (!this._wysiwyg_has_content('#risks_wrapper', 'risks')) {
                this._invalidWysiwyg('#risks_wrapper', 'err_risks');
                hasError = true;
            } else {
                this._validWysiwyg('#risks_wrapper', 'err_risks');
            }

            // Procedure Outcome (WYSIWYG)
            if (!this._wysiwyg_has_content('#results_wrapper', 'results')) {
                this._invalidWysiwyg('#results_wrapper', 'err_results');
                hasError = true;
            } else {
                this._validWysiwyg('#results_wrapper', 'err_results');
            }

            // Product Used
            const pu = document.getElementById('product_used_id');
            if (pu && !pu.value) {
                this._showErr('err_product_used');
                this._invalid(pu);
                hasError = true;
            } else {
                this._hideErr('err_product_used');
                if (pu) this._valid(pu);
            }

            // Date Performed
            const dp = document.getElementById('date_performed');
            if (dp && !dp.value) {
                this._showErr('err_date_performed');
                this._invalid(dp);
                hasError = true;
            } else {
                this._hideErr('err_date_performed');
                if (dp) this._valid(dp);
            }

            if (hasError) {
                ev.preventDefault();
                ev.stopPropagation();
                const first = document.querySelector('.is-invalid');
                if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    },

    // ── 6. Live clear errors as user fills in ─────────────────────
    // Only runs if submit has been attempted (prevents pre-submit flicker)
    _initLiveClear() {
        const map = {
            procedure_type_id : 'err_procedure_type',
            product_used_id   : 'err_product_used',
            date_performed    : 'err_date_performed',
        };
        Object.entries(map).forEach(([id, errId]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', () => {
                if (!this._submitAttempted) return;
                if (el.value) { this._valid(el); this._hideErr(errId); }
                else          { this._invalid(el); this._showErr(errId); }
            });
        });

        const oi = document.getElementById('other_procedure_detail');
        if (oi) {
            oi.addEventListener('input', () => {
                if (!this._submitAttempted) return;
                if (oi.value.trim()) { this._valid(oi); this._hideErr('err_other_detail'); }
                else                 { this._invalid(oi); this._showErr('err_other_detail'); }
            });
        }
    },

    // ── 7. Track which fields the user has touched ────────────────
    // Marks a field as "touched" on blur. After submit, live errors
    // appear for touched fields only — not for ones never visited.
    _initTouchedTracking() {
        const fieldIds = [
            'procedure_type_id', 'product_used_id', 'date_performed',
            'category_specialty', 'doctor_experience', 'duration',
            'duration_unit', 'recovery_period_value', 'recovery_period_unit',
            'risk_level', 'recovery', 'risks', 'results',
            'procedure_description', 'other_procedure_detail',
        ];
        fieldIds.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('blur', () => this._touched.add(id));
        });
    },

    // ── Helpers ───────────────────────────────────────────────────
    _showErr(id) {
        const el = document.getElementById(id);
        if (el) el.classList.remove('d-none');
    },
    _hideErr(id) {
        const el = document.getElementById(id);
        if (el) el.classList.add('d-none');
    },
    _invalid(el) {
        el.classList.add('is-invalid');
        el.classList.remove('is-valid');
    },
    _valid(el) {
        el.classList.remove('is-invalid');
        el.classList.remove('is-valid');
    },

    // ── WYSIWYG helpers ──────────────────────────────────────────
    // Odoo 18 Wysiwyg DOM structure (with resizable:true):
    //   .o_wysiwyg_textarea_wrapper
    //     └── .o_wysiwyg_wrapper.odoo-editor
    //           └── .note-editable   (the contenteditable, has the visible border)
    //           └── .o_wysiwyg_resizer
    //
    // Root cause of CSS approach failing: the .css file is NOT compiled
    // through SCSS in Odoo 18 — $variables and nesting break browser CSS
    // parsing, silently dropping our WYSIWYG rules.
    //
    // Solution: apply the red outline directly as an inline style on the
    // wrapper. Inline styles are always applied, zero CSS dependency.
    // Also show a sibling error message div for unmissable UX.

    _wysiwyg_has_content(wrapperSel, fallbackId) {
        // Check .note-editable (Odoo 18) or .odoo-editor-editable (older)
        const editable = document.querySelector(
            wrapperSel + ' .note-editable, ' +
            wrapperSel + ' .odoo-editor-editable'
        );
        if (editable) {
            // <p><br></p> renders as '\n' — trim() gives '' (empty)
            return editable.innerText.trim().length > 0;
        }
        // WYSIWYG not yet initialised — check raw textarea
        const ta = document.getElementById(fallbackId);
        return ta ? ta.value.trim().length > 0 : true;
    },

    _invalidWysiwyg(wrapperSel, errId) {
        // 1. Apply red outline inline — works regardless of CSS compilation
        const wrapper = document.querySelector(wrapperSel + ' .o_wysiwyg_textarea_wrapper');
        if (wrapper) {
            wrapper.style.outline = '2px solid #dc3545';
            wrapper.style.borderRadius = '4px';
        }
        // 2. Show the sibling error message div
        const errEl = document.getElementById(errId);
        if (errEl) errEl.classList.remove('d-none');
    },

    _validWysiwyg(wrapperSel, errId) {
        const wrapper = document.querySelector(wrapperSel + ' .o_wysiwyg_textarea_wrapper');
        if (wrapper) {
            wrapper.style.outline = '';
            wrapper.style.borderRadius = '';
        }
        const errEl = document.getElementById(errId);
        if (errEl) errEl.classList.add('d-none');
    },

    _clearErrors() {
        ['err_procedure_type', 'err_product_used', 'err_other_detail', 'err_date_performed']
            .forEach(id => this._hideErr(id));
        ['procedure_type_id', 'product_used_id', 'other_procedure_detail', 'date_performed']
            .forEach(id => {
                const el = document.getElementById(id);
                if (el) el.classList.remove('is-invalid', 'is-valid');
            });
        // Clear WYSIWYG inline styles and error messages on toggle-off
        [
            ['#recovery_wrapper', 'err_recovery'],
            ['#risks_wrapper',    'err_risks'],
            ['#results_wrapper',  'err_results'],
        ].forEach(([sel, errId]) => {
            const wrapper = document.querySelector(sel + ' .o_wysiwyg_textarea_wrapper');
            if (wrapper) { wrapper.style.outline = ''; wrapper.style.borderRadius = ''; }
            const errEl = document.getElementById(errId);
            if (errEl) errEl.classList.add('d-none');
        });
    },
});
