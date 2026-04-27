# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class CountryCompliance(models.Model):
    _name = "country.compliance"
    _description = "Country Compliance"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True)
    country_id = fields.Many2one("res.country", string="Country", tracking=True)
    description = fields.Html(string="Description", required=True)

    @api.constrains("country_id")
    def _check_unique_country(self):
        for record in self:
            domain = [("id", "!=", record.id)]
            domain.append(
                (
                    "country_id",
                    "=",
                    record.country_id.id if record.country_id else False,
                )
            )
            if self.search_count(domain) > 0:
                raise ValidationError(
                    "A compliance record already exists for this country."
                )

    def unlink(self):
        for record in self:
            reg = self.env["doctor.registration"].search(
                [("compliance_id", "=", record.id)], limit=1
            )
            if reg:
                raise ValidationError(
                    f"Cannot delete '{record.name}' "
                    f"— used by registration '{reg.name}'."
                )
            partner = self.env["res.partner"].search(
                domain=[
                    ("compliance_id", "=", record.id),
                    ("is_doctor", "=", True),
                ],
                limit=1,
            )
            if partner:
                raise ValidationError(
                    f"Cannot delete '{record.name}' "
                    f"— assigned to doctor '{partner.name}'."
                )
        return super().unlink()

    def write(self, vals):
        """
        When the compliance description changes:
          - Reset compliance_accepted = False on all linked doctors
          who had accepted.
            Doctors already at False remain False (no change needed there).
          - Post chatter note on compliance and on each affected partner.

        When country_id changes on the compliance record:
          - The compliance record now applies to a different country.
          - Reset compliance_accepted = False on all previously linked doctors.
          - Post chatter notes.
        """
        description_changing = "description" in vals

        # ── Capture old text for comparison (description change)
        old_texts = {}
        if description_changing:
            for record in self:
                old_texts[record.id] = html2plaintext(record.description or "").strip()

        result = super().write(vals)

        for record in self:
            # ── Description changed
            if description_changing:
                new_text = html2plaintext(vals["description"] or "").strip()
                if old_texts.get(record.id) == new_text:
                    continue  # no real change

                record.message_post(
                    body=Markup(
                        "📝 <b>Description updated</b> for country: " "<b>{country}</b>"
                    ).format(country=record.country_id.name or "Global"),
                    subtype_xmlid="mail.mt_note",
                )

                # Only reset doctors who HAD accepted: already-False = False
                doctors = (
                    self.env["res.partner"]
                    .sudo()
                    .search(
                        [
                            ("is_doctor", "=", True),
                            ("compliance_accepted", "=", True),
                            "|",
                            ("compliance_id", "=", record.id),
                            ("country_id", "=", record.country_id.id),
                        ]
                    )
                )
                if doctors:
                    doctors.write({"compliance_accepted": False})
                    for doctor in doctors:
                        doctor.message_post(
                            body=Markup(
                                "⚠️ <b>Compliance Updated</b>: "
                                "Country compliance for <b>{country}</b> "
                                "has changed. Re-acceptance required."
                            ).format(country=record.country_id.name or "Global"),
                            subtype_xmlid="mail.mt_note",
                        )

                # Also reset on linked doctor.registration records
                regs = (
                    self.env["doctor.registration"]
                    .sudo()
                    .search(
                        [
                            ("compliance_id", "=", record.id),
                            ("compliance_accepted", "=", True),
                        ]
                    )
                )
                if regs:
                    regs.write({"compliance_accepted": False})

                _logger.info(
                    "country.compliance %s: description changed, "
                    "reset %d doctor(s).",
                    record.id,
                    len(doctors),
                )

        return result
