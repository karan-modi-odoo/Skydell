# -*- coding: utf-8 -*-
from odoo import api, models, fields
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_doctor = fields.Boolean(string="Is Doctor?", readonly=True)

    # ── Medical profile (copied from doctor.registration on approval) ──
    specialty_id = fields.Many2one("doctor.specialty", string="Medical Specialty")
    experience = fields.Integer(string="Years of Clinical Experience")
    license_number = fields.Char(string="Medical License Number")
    license_document = fields.Binary(string="Medical License Document")
    license_filename = fields.Char(string="License File Name")
    license_document_ids = fields.Many2many(
        "ir.attachment",
        "res_partner_license_attachment_rel",
        "partner_id",
        "attachment_id",
        string="License Documents",
    )
    license_expiry_date = fields.Date(string="Medical License Expiry Date")
    reminder_1_days = fields.Integer(
        string="First Reminder (Days Before Expiry)",
        default=0,
    )
    reminder_2_days = fields.Integer(
        string="Second Reminder (Days Before Expiry)",
        default=0,
    )

    # ── Compliance ───────────────────────────────────────────────
    compliance_id = fields.Many2one(
        comodel_name="country.compliance", string="Compliance"
    )
    compliance_accepted = fields.Boolean(string="Compliance Accepted?", tracking=True)
    compliance_accepted_on = fields.Datetime(string="Accepted On")

    country_change_old_name = fields.Char(
        string="Previous Country (before last change)",
        copy=False,
    )

    def _find_compliance_for_country(self, country_id):
        Compliance = self.env["country.compliance"].sudo()
        if country_id:
            rec = Compliance.search(domain=[("country_id", "=", country_id)], limit=1)
            if rec:
                return rec
        return Compliance.search([("country_id", "=", False)], limit=1)

    def write(self, vals):
        country_changing = "country_id" in vals and self.country_id != vals.get(
            "country_id"
        )
        company_changing = "parent_id" in vals and self.parent_id != vals.get(
            "parent_id"
        )

        old_country_map = {}
        if country_changing:
            for rec in self.filtered("is_doctor"):
                old_country_map[rec.id] = (
                    rec.country_id.id,
                    rec.country_id.name or "N/A",
                )

        result = super().write(vals)

        # ── Country changed
        if country_changing:
            for rec in self.filtered("is_doctor"):
                old_cid, old_cname = old_country_map.get(rec.id, (False, "N/A"))
                new_cid = rec.country_id.id
                if old_cid == new_cid:
                    continue

                new_cname = rec.country_id.name or "N/A"
                compliance = rec._find_compliance_for_country(new_cid)

                # 1. Update partner
                super(ResPartner, rec).write(
                    {
                        "compliance_id": (compliance.id if compliance else False),
                        "compliance_accepted": False,
                        "country_change_old_name": old_cname,
                    }
                )

                # 2. Sync back to doctor.registration
                #    skip_partner_sync prevents a write loop
                if not self.env.context.get("skip_partner_sync"):
                    reg = (
                        self.env["doctor.registration"]
                        .sudo()
                        .search(
                            domain=[("user_id.partner_id", "=", rec.id)],
                            limit=1,
                        )
                    )
                    if reg:
                        reg.with_context(skip_partner_sync=True).write(
                            {
                                "country_id": new_cid,
                                "compliance_id": (
                                    compliance.id if compliance else False
                                ),
                                "compliance_accepted": False,
                                "country_change_old_name": old_cname,
                            }
                        )
                        reg.message_post(
                            body=Markup(
                                "🌍 <b>Country Changed (via Contact)</b>: "
                                "updated from <b>{old}</b> → <b>{new}</b>. "
                                "<b>Compliance</b> updated to <b>{comp}</b>. "
                                "<b>Compliance Accepted?</b> "
                                "reset to <b>No</b>."
                            ).format(
                                old=old_cname,
                                new=new_cname,
                                comp=compliance.name if compliance else "N/A",
                            ),
                            subtype_xmlid="mail.mt_note",
                        )

                rec.message_post(
                    body=Markup(
                        "🌍 <b>Country Changed</b>: updated from "
                        "<b>{old}</b> → <b>{new}</b>. "
                        "<b>Compliance Accepted?</b> reset to <b>No</b>. "
                        "Doctor must re-accept compliance."
                    ).format(old=old_cname, new=new_cname),
                    subtype_xmlid="mail.mt_note",
                )
                _logger.info(
                    "res.partner %s (doctor): "
                    "country %s → %s, synced to registration.",
                    rec.id,
                    old_cname,
                    new_cname,
                )

        # ── Company changed
        if company_changing and not country_changing:
            for rec in self.filtered("is_doctor"):
                company = rec.parent_id
                cid = company.country_id.id if company and company.country_id else False
                compliance = rec._find_compliance_for_country(cid)

                if compliance and (
                    rec.compliance_id.id != compliance.id or rec.compliance_accepted
                ):
                    super(ResPartner, rec).write(
                        {
                            "compliance_id": compliance.id,
                            "compliance_accepted": False,
                        }
                    )

                    reg = (
                        self.env["doctor.registration"]
                        .sudo()
                        .search(
                            domain=[("user_id.partner_id", "=", rec.id)],
                            limit=1,
                        )
                    )
                    if reg:
                        reg.with_context(skip_partner_sync=True).write(
                            {
                                "compliance_id": compliance.id,
                                "compliance_accepted": False,
                            }
                        )
                        reg.message_post(
                            body=Markup(
                                "🏢 <b>Company Changed (via Contact)</b>: "
                                "Compliance updated to <b>{comp}</b>. "
                                "<b>Compliance Accepted?</b> "
                                "reset to <b>No</b>."
                            ).format(comp=compliance.name),
                            subtype_xmlid="mail.mt_note",
                        )

                    company_name = company.name if company else "N/A"
                    country_name = (
                        company.country_id.name
                        if company and company.country_id
                        else "N/A"
                    )
                    rec.message_post(
                        body=Markup(
                            "🏢 <b>Company Changed</b>: linked to <b>{co}</b> "
                            "(country: <b>{ct}</b>). "
                            "Compliance updated and <b>"
                            "Compliance Accepted?</b> "
                            "reset to <b>No</b>."
                        ).format(co=company_name, ct=country_name),
                        subtype_xmlid="mail.mt_note",
                    )

        return result

    # ------------------------------------------------------------------
    # License expiry reminders
    # ------------------------------------------------------------------

    @staticmethod
    def _days_label(days):
        """Return human-readable label e.g. '1 day', '5 days'."""
        return "{} day{}".format(days, "s" if days != 1 else "")

    def _send_reminder_email(self, template, reminder_num, days):
        """Send a single reminder email and post a chatter note."""
        period_label = self._days_label(days)
        template.with_context(reminder_period=period_label).send_mail(
            self.id, force_send=True
        )
        self.message_post(
            body=Markup(
                "📧 Reminder {num} ({timing}) license expiry reminder"
                " sent to <b>{email}</b>."
            ).format(num=reminder_num, timing=period_label, email=self.email),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    @api.model
    def action_send_license_expiry_reminders(self):
        today = fields.Date.today()

        template = self.env.ref(
            "adx_doctor_registration_portal." "mail_template_license_expiry_reminder",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning(
                "License expiry reminder template not found — skipping cron."
            )
            return

        doctors = self.search(
            [
                ("is_doctor", "=", True),
                ("license_expiry_date", "!=", False),
            ]
        )

        for partner in doctors:
            target_date_1 = today + relativedelta(days=partner.reminder_1_days)
            target_date_2 = today + relativedelta(days=partner.reminder_2_days)
            if (
                partner.reminder_1_days > 0
                and partner.license_expiry_date == target_date_1
            ):
                partner._send_reminder_email(template, 1, partner.reminder_1_days)
            if (
                partner.reminder_2_days > 0
                and partner.license_expiry_date == target_date_2
            ):
                partner._send_reminder_email(template, 2, partner.reminder_2_days)
