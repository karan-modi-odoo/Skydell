# -*- coding: utf-8 -*-
import base64
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError
from werkzeug.urls import url_encode


class DoctorRegistrationController(http.Controller):

    @http.route(
        "/doctor-registration", type="http", auth="public", website=True
    )
    def doctor_registration_page(self, **kw):
        # Only allow public (unauthenticated) users
        if not request.env.user._is_public():
            if request.env.user.has_group('base.group_user'):
                return request.redirect('/web')
            return request.redirect('/my')
        return request.render(
            "adx_doctor_registration_portal.doctor_registration_page"
        )

    @http.route(
        "/submit-doctor-registration",
        type="http",
        auth="public",
        website=True,
        csrf=True,
        methods=["POST"],
    )
    def submit_doctor_registration(self, **post):
        # Handle multiple file uploads
        license_files = request.httprequest.files.getlist("license_document")

        # For backward compatibility - store first file in legacy Binary field
        license_data = False
        license_filename = False

        if license_files and len(license_files) > 0:
            first_file = license_files[0]
            if first_file and first_file.filename:
                first_file.seek(0)
                license_data = base64.b64encode(first_file.read())
                license_filename = first_file.filename

        status = {}
        try:
            email = post.get("email", "").strip().lower()

            existing_registration = (
                request.env["doctor.registration"]
                .sudo()
                .search(
                    [
                        ("email", "=", email),
                    ],
                    limit=1,
                )
            )

            if existing_registration:
                status = {
                    "success": "0",
                    "msg_title": "Already Registered",
                    "msg": "A registration request with this email address "
                           "already exists. Please use a different email "
                           "or contact support.",
                }
                return request.redirect(
                    "/doctor-registration-thank-you?" + url_encode(status)
                )

            existing_partner = (
                request.env["res.partner"]
                .sudo()
                .search(
                    [
                        ("email", "=", email),
                        ("is_doctor", "=", True),
                    ],
                    limit=1,
                )
            )

            if existing_partner:
                status = {
                    "success": "0",
                    "msg_title": "Account Exists",
                    "msg": "An account with this email already exists. "
                           "Please log in instead.",
                }
                return request.redirect(
                    "/doctor-registration-thank-you?" + url_encode(status)
                )

            registration = (
                request.env["doctor.registration"]
                .sudo()
                .create(
                    {
                        "name": post.get("name"),
                        "email": post.get("email"),
                        "phone": (
                            (
                                    post.get("phone_country_code", "").strip()
                                    + " "
                                    + post.get("phone", "").strip()
                            ).strip()
                            if post.get("phone")
                            else False
                        ),
                        "specialty": (
                            self._safe_int(post.get("specialty"))
                            if post.get("specialty")
                            else False
                        ),
                        "experience": (
                            self._safe_int(post.get("experience"), default=0)
                            if post.get("experience")
                            else 0
                        ),
                        "country_id": (
                            self._safe_int(post.get("country_id"))
                            if post.get("country_id")
                            else False
                        ),
                        "license_number": post.get("license_number"),
                        "license_document": license_data,
                        "license_filename": license_filename,
                        "license_expiry_date": post.get("license_expiry_date")
                                               or False,
                        "compliance_id": self._resolve_compliance_id(
                            post.get("compliance_id")
                        ),
                        "compliance_accepted": bool(
                            post.get("compliance_accepted")
                        ),
                        "status": "pending",
                    }
                )
            )

            # Create attachments for all uploaded files
            attachment_ids = []
            for file in license_files:
                if file and file.filename:
                    file.seek(0)
                    file_content = file.read()
                    if file_content:
                        attachment = (
                            request.env["ir.attachment"]
                            .sudo()
                            .create(
                                {
                                    "name": file.filename,
                                    "type": "binary",
                                    "datas": base64.b64encode(file_content),
                                    "res_model": "doctor.registration",
                                    "res_id": registration.id,
                                }
                            )
                        )
                        attachment_ids.append(attachment.id)

            # Link attachments to registration
            if attachment_ids:
                registration.sudo().write(
                    {"license_document_ids": [(6, 0, attachment_ids)]}
                )

            status = {"success": "1"}
        except ValidationError as e:
            status = {
                "success": "0",
                "msg_title": "Validation Error",
                "msg": str(e),
            }
        except Exception as e:
            status = {
                "success": "0",
                "msg_title": "Registration Failed",
                "msg": str(e),
            }

        return request.redirect(
            "/doctor-registration-thank-you?" + url_encode(status)
        )

    @staticmethod
    def _safe_int(value, default=False):
        """Convert a form value to int safely, returning *default* on failure."""
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def _resolve_compliance_id(self, raw_value):
        """Return compliance ID from form,
        falling back to the global default."""
        if raw_value:
            return self._safe_int(raw_value)
        fallback = (
            request.env["country.compliance"]
            .sudo()
            .search([("country_id", "=", False)], limit=1)
        )
        return fallback.id if fallback else False

    @http.route(
        "/doctor-registration-thank-you",
        type="http",
        auth="public",
        website=True,
    )
    def doctor_registration_thank_you(self, **kw):
        return request.render(
            "adx_doctor_registration_portal.doctor_registration_thank_you", kw
        )

    @http.route(
        "/check-compliance-accepted", type="json", auth="user", csrf=False
    )
    def check_compliance_accepted(self, **kw):
        """
        Called on every portal page load for logged-in doctors.

        Returns:
          regenerated  : True when the popup must be shown
          old_country  : previous country name (only when a country
          change triggered this)
          new_country  : current country name  (only when a country
          change triggered this)
          description  : compliance HTML (always included when
          regenerated=True)

        Popup display rules (all use the same single popup):
          • old_country + new_country present
          → show country-change banner + description
          • old_country absent
          → show description-updated banner only
        """
        partner = request.env.user.partner_id
        if not (partner.is_doctor and not partner.compliance_accepted):
            return {"regenerated": False}

        old_country = None
        new_country = None

        # Priority 1 — country changed via backend doctor.registration form
        reg = (
            request.env["doctor.registration"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        if reg and reg.country_change_old_name:
            old_country = reg.country_change_old_name
            new_country = partner.country_id.name or "N/A"

        # Priority 2 — country changed from portal profile
        # (res.partner.write override)
        elif partner.country_change_old_name:
            old_country = partner.country_change_old_name
            new_country = partner.country_id.name or "N/A"

        return {
            "regenerated": True,
            "old_country": old_country,  # None → description-only change
            "new_country": new_country,  # None → description-only change
            "description": partner.compliance_id.description or "",
        }

    @http.route(
        "/accept-regenerated-compliance",
        type="json",
        auth="user",
        website=True,
    )
    def accept_regenerated_compliance(self, **kw):
        """
        Called when the doctor clicks Accept on the compliance popup.
        Sets compliance_accepted = True and clears all country-change flags.
        """
        partner = request.env.user.partner_id.sudo()
        partner.write(
            {
                "compliance_accepted": True,
                "compliance_accepted_on": fields.Datetime.now(),
                "country_change_old_name": False,  # Clear portal-side flag
            }
        )

        # Sync back to doctor.registration and clear its flag too
        reg = (
            request.env["doctor.registration"]
            .sudo()
            .search([("user_id", "=", request.env.user.id)], limit=1)
        )
        if reg:
            reg.write(
                {
                    "compliance_accepted": True,
                    "country_change_old_name": False,
                }
            )

        return {"success": "1"}

    @http.route(
        "/get-country-compliance", type="json", auth="public", csrf=False
    )
    def get_country_compliance(self, country_id=None, **kw):
        """
        Return compliance for the given country.
        Falls back to the global default (no country) if no match found.
        """
        Compliance = request.env["country.compliance"].sudo()

        compliance = (
            Compliance.search(
                [("country_id", "=", int(country_id))], limit=1
            )
            if country_id
            else Compliance.browse()
        )

        if not compliance:
            compliance = Compliance.search(
                [("country_id", "=", False)], limit=1
            )

        if compliance:
            return {
                "compliance_id": compliance.id,
                "description": compliance.description or "",
                "has_compliance": True,
            }
        return {
            "compliance_id": False,
            "description": "",
            "has_compliance": False,
        }
