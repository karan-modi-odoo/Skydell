# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError
from markupsafe import Markup


class RegistrationRejectWizard(models.TransientModel):
    _name = "registration.reject.wizard"
    _description = "Reject Registration"

    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_reject(self):
        if not self.env.user.has_group(
            "adx_doctor_registration_portal.group_doctor_manager"
        ):
            raise UserError("Only Doctor Managers can reject registrations.")

        records = self.env["doctor.registration"].browse(
            self.env.context.get("active_ids", [])
        )
        template = self.env.ref(
            "adx_doctor_registration_portal."
            "mail_template_doctor_registration_reject"
        )

        for record in records:
            if record.status != "pending":
                raise UserError(
                    "You can only reject registrations that are Pending."
                )

            record.write(
                {
                    "status": "rejected",
                    "rejection_reason": self.rejection_reason,
                    "rejected_by": self.env.user.id,
                    "rejection_date": fields.Datetime.now(),
                }
            )
            template.with_context(
                rejection_reason=self.rejection_reason
            ).send_mail(record.id, force_send=True)

            record.message_post(
                body=Markup(
                    "Registration <b>Rejected</b>.<br/>"
                    "<b>Reason:</b> {reason}<br/>"
                    "Email sent to <b>{email}</b>."
                ).format(
                    reason=self.rejection_reason or "(none)",
                    email=record.email or "(empty)",
                ),
                subtype_xmlid="mail.mt_comment",
            )

        return {"type": "ir.actions.act_window_close"}
