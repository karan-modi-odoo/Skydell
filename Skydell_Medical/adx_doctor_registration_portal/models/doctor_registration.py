# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
import logging
import re

_logger = logging.getLogger(__name__)


class DoctorRegistration(models.Model):
    _name = "doctor.registration"
    _description = "Doctor Registration Request"
    _rec_name = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    @api.constrains("email")
    def _check_email_format(self):
        """Validate email format."""
        for record in self:
            if record.email and not re.match(
                r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
                record.email.strip(),
            ):
                raise ValidationError(
                    f"The email address '{record.email}' is not valid. "
                    f"Please enter a valid professional email address."
                )

    @api.constrains("email")
    def _check_unique_email(self):
        for record in self:
            duplicate = self.env["doctor.registration"].search(
                [
                    ("email", "=", record.email),
                    ("id", "!=", record.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    f"A registration request with email address "
                    f"'{record.email}' already exists.\n"
                    f"Please contact support if you believe this is an error."
                )

    name = fields.Char(
        string="Full Name (as per medical license)",
        required=True,
        tracking=True,
    )
    email = fields.Char(
        string="Professional Email Address", required=True, tracking=True
    )
    phone = fields.Char(string="Contact Number", required=True)
    specialty = fields.Many2one(
        "doctor.specialty", string="Medical Specialty", required=True
    )
    experience = fields.Integer(string="Years of Clinical Experience", required=True)
    country_id = fields.Many2one(
        "res.country", string="Country of Medical Practice", required=True
    )

    license_number = fields.Char(string="Medical License Number", required=True)
    license_document = fields.Binary(string="Medical License Document", required=True)
    license_filename = fields.Char(string="License File Name")
    # Multiple license documents stored as attachments
    license_document_ids = fields.Many2many(
        "ir.attachment",
        "doctor_registration_attachment_rel",
        "registration_id",
        "attachment_id",
        string="License Documents",
    )

    compliance_accepted = fields.Boolean(
        string="Compliance Accepted?", required=True, tracking=True
    )
    compliance_id = fields.Many2one(
        "country.compliance", string="Compliance", tracking=True
    )

    status = fields.Selection(
        [
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="pending",
        tracking=True,
    )

    license_expiry_date = fields.Date(
        string="Medical License Expiry Date",
        required=True,
        tracking=True,
    )
    reminder_1_days = fields.Integer(
        string="First Reminder (Days Before Medical License Expiry)",
        default=0,
        tracking=True,
        help="Number of days before license expiry date to send "
        "the first reminder email.",
    )

    reminder_2_days = fields.Integer(
        string="Second Reminder (Days Before Medical License Expiry)",
        default=0,
        tracking=True,
        help="Number of days before license expiry date to send the "
        "second reminder email.",
    )

    approved_by = fields.Many2one("res.users", string="Approved By", tracking=True)
    approval_date = fields.Datetime(string="Approval Date", tracking=True)
    rejected_by = fields.Many2one("res.users", string="Rejected By", tracking=True)
    rejection_date = fields.Datetime(string="Rejection Date", tracking=True)
    rejection_reason = fields.Text(string="Rejection Reason", tracking=True)
    user_id = fields.Many2one("res.users", string="Portal User", readonly=True)

    # Stores the old country name when admin changes country_id from backend.
    # Drives the "old → new" country banner in the compliance popup.
    # Cleared when the doctor re-accepts compliance.
    country_change_old_name = fields.Char(
        string="Previous Country (before last change)",
        copy=False,
    )

    @api.constrains(
        "experience",
        "reminder_1_days",
        "reminder_2_days",
    )
    def _check_experience_positive(self):
        for record in self:
            if record.experience < 0:
                raise ValidationError(
                    "Years of clinical experience cannot be a negative value."
                )
            if record.reminder_1_days < 0:
                raise ValidationError("Reminder days cannot be a negative value.")
            if record.reminder_2_days < 0:
                raise ValidationError("Reminder days cannot be a negative value.")

    def action_approve(self):
        if not self.env.user.has_group(
            "adx_doctor_registration_portal.group_doctor_manager"
        ):
            raise UserError("Only Doctor Managers can approve registrations.")

        portal_group = self.env.ref("base.group_portal")

        for record in self:
            if record.status != "pending":
                raise UserError("You can only approve registrations that are Pending.")

            partner = self.env["res.partner"].search(
                [("email", "=", record.email), ("is_company", "=", False)],
                limit=1,
            )
            doctor_vals = {
                "is_doctor": True,
                "specialty_id": record.specialty.id,
                "experience": record.experience,
                "license_number": record.license_number,
                "license_document": record.license_document,
                "license_filename": record.license_filename,
                "license_document_ids": [(6, 0, record.license_document_ids.ids)],
                "license_expiry_date": record.license_expiry_date,
                "reminder_1_days": record.reminder_1_days,
                "reminder_2_days": record.reminder_2_days,
                "compliance_id": record.compliance_id.id,
                "compliance_accepted": record.compliance_accepted,
                "compliance_accepted_on": record.create_date,
            }
            if not partner:
                partner = self.env["res.partner"].create(
                    {
                        "name": record.name,
                        "email": record.email,
                        "phone": record.phone,
                        "country_id": record.country_id.id,
                        "company_type": "person",
                        **doctor_vals,
                    }
                )
            else:
                partner.write(doctor_vals)

            user = self.env["res.users"].search([("login", "=", record.email)], limit=1)
            if not user:
                user = self.env["res.users"].create(
                    {
                        "name": record.name,
                        "login": record.email,
                        "email": record.email,
                        "partner_id": partner.id,
                        "groups_id": [(6, 0, [portal_group.id])],
                    }
                )

            record.user_id = user.id
            record.write(
                {
                    "status": "approved",
                    "approved_by": self.env.user.id,
                    "approval_date": fields.Datetime.now(),
                }
            )

            try:
                user.action_reset_password()
            except Exception as e:
                # Log error but don't block approval
                record.message_post(
                    body=Markup(
                        "⚠️ Password reset email failed: <b>{error}</b><br/>"
                        "User can reset manually from login page."
                    ).format(error=str(e)),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

            template = self.env.ref(
                "adx_doctor_registration_portal."
                "mail_template_doctor_registration_approve",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(record.id, force_send=True)

            record.message_post(
                body=Markup(
                    "Registration <b>Approved</b>. "
                    "Password setup email sent to <b>{email}</b>."
                ).format(email=record.email),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def action_open_reject_wizard(self):
        return {
            "name": "Reject Registration",
            "type": "ir.actions.act_window",
            "res_model": "registration.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_ids": self.ids},
        }

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _find_compliance_for_country(self, country_id):
        """Return best-matching country.compliance
        (exact match or global default)."""
        Compliance = self.env["country.compliance"].sudo()
        if country_id:
            rec = Compliance.search(domain=[("country_id", "=", country_id)], limit=1)
            if rec:
                return rec
        return Compliance.search([("country_id", "=", False)], limit=1)

    def write(self, vals):
        """
        When country_id is changed from the backend doctor.registration form:
          1. Resolve the matching compliance for the new country
          → update compliance_id.
          2. Reset compliance_accepted = False on this registration.
          3. Store old country name in country_change_old_name.
          4. Sync all of the above to the linked res.partner portal account.
          5. Post chatter notes on both records.
        """
        country_changing = "country_id" in vals

        # Capture old country BEFORE super().write()
        old_country_map = {}
        if country_changing:
            for rec in self:
                old_country_map[rec.id] = (
                    rec.country_id.id,
                    rec.country_id.name or "N/A",
                )

        result = super().write(vals)

        if country_changing:
            for rec in self:
                new_cid = rec.country_id.id
                old_cid, old_cname = old_country_map.get(rec.id, (False, "N/A"))
                if new_cid == old_cid:
                    continue

                new_cname = rec.country_id.name or "N/A"
                compliance = rec._find_compliance_for_country(new_cid)

                _logger.info(
                    "doctor.registration %s: " "country %s → %s, compliance reset.",
                    rec.id,
                    old_cname,
                    new_cname,
                )

                # 1. Update registration (super to avoid recursion)
                super(DoctorRegistration, rec).write(
                    {
                        "compliance_id": (compliance.id if compliance else False),
                        "compliance_accepted": False,
                        "country_change_old_name": old_cname,
                    }
                )

                # 2. Sync to linked portal partner
                if (
                    rec.user_id
                    and rec.user_id.partner_id
                    and not self.env.context.get("skip_partner_sync")
                ):
                    rec.user_id.partner_id.sudo().write(
                        {
                            "compliance_id": (compliance.id if compliance else False),
                            "compliance_accepted": False,
                            "country_change_old_name": old_cname,
                        }
                    )
                    rec.user_id.partner_id.sudo().message_post(
                        body=Markup(
                            "⚠️ <b>Country Changed (by admin)</b>: "
                            "Country of medical practice updated from "
                            "<b>{old}</b> → <b>{new}</b>. "
                            "<b>Compliance Accepted?</b> reset to <b>No</b>. "
                            "Doctor must re-accept on next login."
                        ).format(old=old_cname, new=new_cname),
                        subtype_xmlid="mail.mt_note",
                    )

                # 3. Chatter on registration record
                rec.message_post(
                    body=Markup(
                        "⚠️ <b>Country Changed</b>: Updated from "
                        "<b>{old}</b> → <b>{new}</b>. "
                        "<b>Compliance Accepted?</b> "
                        "automatically reset to <b>No</b>."
                    ).format(old=old_cname, new=new_cname),
                    subtype_xmlid="mail.mt_note",
                )

        return result

    def action_open_user(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Users",
            "res_model": "res.users",
            "view_mode": "form",
            "res_id": self.user_id.id,
        }
