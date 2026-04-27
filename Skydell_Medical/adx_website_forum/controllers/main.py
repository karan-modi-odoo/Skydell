# -*- coding: utf-8 -*-
import logging
from odoo import http, tools
from odoo.http import request
from odoo.addons.website_forum.controllers.website_forum import WebsiteForum

_logger = logging.getLogger(__name__)


class WebsiteForumInherit(WebsiteForum):

    @http.route(
        '/forum/<model("forum.forum"):forum>/post/'
        '<model("forum.post"):post>/comment',
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def post_comment(self, forum, post, **kwargs):
        question = post.parent_id or post
        comment_body = kwargs.get("comment", "")

        if comment_body and post.forum_id.id == forum.id:
            post_owner = question.create_uid
            commenter = request.env.user

            if post_owner.id != commenter.id and post_owner.email:
                self._send_comment_notification(
                    post=question,
                    comment=comment_body,
                    commenter_name=commenter.name,
                    post_owner=post_owner,
                    forum=forum,
                )
                question.sudo().message_unsubscribe(
                    partner_ids=[post_owner.partner_id.id]
                )

        return super().post_comment(forum, post, **kwargs)

    def _send_comment_notification(
        self, post, comment, commenter_name, post_owner, forum
    ):
        """Send comment notification email to the post owner."""
        template = request.env.ref(
            "adx_website_forum.email_template_forum_comment",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning(
                "adx_website_forum: email_template_forum_comment "
                "not found. No comment notification sent for post %s.",
                post.id,
            )
            return

        base_url = (
            request.env["ir.config_parameter"].sudo().get_param("web.base.url")
        )
        slug = request.env["ir.http"]._slug
        post_url = f"{base_url}/forum/{slug(forum)}/{slug(post)}"
        company_email = request.env.company.email or "noreply@example.com"

        template.sudo().with_context(
            commenter_name=commenter_name,
            post_owner_name=post_owner.name,
            post_name=post.name,
            comment_content=tools.mail.plaintext2html(comment),
            post_url=post_url,
        ).send_mail(
            post.id,
            force_send=True,
            email_values={
                "email_to": post_owner.email,
                "email_from": company_email,
            },
        )

    @http.route(
        ['/forum/<model("forum.forum"):forum>/ask'],
        type="http",
        auth="user",
        website=True,
    )
    def forum_post(self, forum, **post):
        response = super().forum_post(forum, **post)

        if hasattr(response, "qcontext"):
            doctor_reg = (
                request.env["doctor.registration"]
                .sudo()
                .search([("user_id", "=", request.env.user.id)], limit=1)
            )
            response.qcontext.update(
                {
                    "procedure_types": request.env["procedure.type"]
                    .sudo()
                    .search([("active", "=", True)]),
                    "skydell_products": request.env["product.template"]
                    .sudo()
                    .search([], limit=100),
                    "is_new_post": True,
                    "doctor_reg": doctor_reg,
                }
            )
        return response

    @http.route(
        [
            '/forum/<model("forum.forum"):forum>/new',
            '/forum/<model("forum.forum"):forum>/'
            '<model("forum.post"):post_parent>/reply',
        ],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def post_create(self, forum, post_parent=None, **post):
        response = super().post_create(forum, post_parent=post_parent, **post)

        # Only process top-level questions (not replies)
        if not post_parent:
            new_post = (
                request.env["forum.post"]
                .sudo()
                .search(
                    [
                        ("create_uid", "=", request.env.user.id),
                        ("forum_id", "=", forum.id),
                        ("parent_id", "=", False),
                    ],
                    order="id desc",
                    limit=1,
                )
            )
            if new_post:
                vals = {
                    "compliance_confirmation": bool(
                        post.get("compliance_confirmation")
                    ),
                    "specialty_id": self._get_doctor_specialty_id(
                        request.env.user
                    ),
                    "topic_type_id": self._safe_int(post.get("topic_type_id")),
                }
                if bool(post.get("is_procedure_post")):
                    vals.update(self._prepare_procedure_vals(post))
                new_post.sudo().write(vals)

        return response

    @http.route(
        '/forum/<model("forum.forum"):forum>/post/'
        '<model("forum.post"):post>/save',
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def post_save(self, forum, post, **kwargs):
        # Strip custom fields from kwargs so Odoo's base post_save only
        # touches name / content / tags (avoids re-wrapping HTML fields).
        custom_keys = {
            "topic_type_id",
            "is_procedure_post",
            "procedure_type_id",
            "procedure_description",
            "other_procedure_detail",
            "other_procedure_description",
            "product_used_id",
            "date_performed",
            "results",
            "compliance_confirmation",
            "specialty_id",
            "doctor_experience",
            "recovery",
            "risks",
            "recovery_period_value",
            "recovery_period_unit",
            "risk_level",
            "duration",
            "duration_unit",
        }
        base_kwargs = {k: v for k, v in kwargs.items() if k not in custom_keys}
        response = super().post_save(forum, post, **base_kwargs)

        # Build a single vals dict — one write instead of many
        vals = {
            "compliance_confirmation": bool(
                kwargs.get("compliance_confirmation")
            ),
            "specialty_id": self._get_doctor_specialty_id(post.create_uid),
        }

        if bool(kwargs.get("is_procedure_post")):
            vals.update(self._prepare_procedure_vals(kwargs))
        else:
            vals.update(
                {
                    "topic_type_id": self._safe_int(
                        kwargs.get("topic_type_id")
                    ),
                    "is_procedure_post": False,
                    "procedure_type_id": False,
                    "procedure_description": None,
                    "other_procedure_detail": False,
                    "product_used_id": False,
                    "date_performed": False,
                    "results": None,
                    "doctor_experience": 0,
                    "duration": 0,
                    "duration_unit": False,
                    "recovery": None,
                    "recovery_period_value": 0,
                    "recovery_period_unit": False,
                    "risk_level": False,
                    "risks": None,
                }
            )

        post.sudo().write(vals)
        _logger.info(
            "Saved fields on post %s (procedure=%s).",
            post.id,
            vals.get("is_procedure_post", False),
        )
        return response

    # ══════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _safe_int(value, default=False):
        """Convert a form value to int, returning *default* on failure."""
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def _get_doctor_specialty_id(self, user):
        """Return the specialty id from the partner linked to *user*."""
        partner = user.sudo().partner_id
        if partner and partner.specialty_id:
            return partner.specialty_id.id
        # Backfill: copy from doctor.registration for partners approved
        # before specialty_id was added to res.partner.
        doctor_reg = (
            request.env["doctor.registration"]
            .sudo()
            .search([("user_id", "=", user.id)], limit=1)
        )
        if doctor_reg and doctor_reg.specialty:
            if partner:
                partner.write({"specialty_id": doctor_reg.specialty.id})
            return doctor_reg.specialty.id
        return False

    def _prepare_procedure_vals(self, data):
        """Build and return a vals dict for procedure-related fields."""
        vals = {"is_procedure_post": True}
        other_detail = (data.get("other_procedure_detail") or "").strip()
        other_desc = data.get("other_procedure_description") or ""
        raw_results = (data.get("results") or "").strip()

        # ── Topic Type ───────────────────────────────────────────
        vals["topic_type_id"] = self._safe_int(data.get("topic_type_id"))

        # ── Duration ─────────────────────────────────────────────
        vals["duration"] = self._safe_int(data.get("duration"), default=0)
        vals["duration_unit"] = data.get("duration_unit") or "hours"

        # ── Procedure Type ───────────────────────────────────────
        if other_detail:
            ProcType = request.env["procedure.type"].sudo()
            existing = ProcType.search(
                [("name", "=ilike", other_detail)], limit=1
            )
            if existing:
                proc_type = existing
                if other_desc:
                    existing.write({"description": other_desc})
                _logger.info(
                    "Reusing procedure.type '%s' (id=%s).",
                    other_detail,
                    existing.id,
                )
            else:
                create_vals = {
                    "name": other_detail,
                    "active": True,
                    "sequence": 10,
                    "is_other": False,
                }
                if other_desc:
                    create_vals["description"] = other_desc
                proc_type = ProcType.create(create_vals)
                _logger.info(
                    "Created procedure.type '%s' (id=%s).",
                    other_detail,
                    proc_type.id,
                )
            vals["procedure_type_id"] = proc_type.id
            vals["procedure_description"] = other_desc or (
                proc_type.description or ""
            )
            vals["other_procedure_detail"] = other_detail
            vals["results"] = raw_results or False
        else:
            proc_id = self._safe_int(data.get("procedure_type_id"))
            vals["procedure_type_id"] = proc_id
            vals["other_procedure_detail"] = False

            user_desc = (data.get("procedure_description") or "").strip()
            if user_desc:
                vals["procedure_description"] = user_desc
                if proc_id:
                    proc_rec = (
                        request.env["procedure.type"].sudo().browse(proc_id)
                    )
                    if proc_rec.exists():
                        proc_rec.write({"description": user_desc})
            elif proc_id:
                proc_rec = request.env["procedure.type"].sudo().browse(proc_id)
                vals["procedure_description"] = (
                    proc_rec.description or "" if proc_rec.exists() else ""
                )
            else:
                vals["procedure_description"] = ""
            vals["results"] = raw_results or False

        # ── Product Used ─────────────────────────────────────────
        vals["product_used_id"] = self._safe_int(data.get("product_used_id"))

        # ── Date Performed ───────────────────────────────────────
        date_val = (data.get("date_performed") or "").strip()
        vals["date_performed"] = date_val or False

        # ── Doctor Experience ────────────────────────────────────
        vals["doctor_experience"] = self._safe_int(
            data.get("doctor_experience"), default=0
        )

        # ── Recovery ─────────────────────────────────────────────
        raw_recovery = (data.get("recovery") or "").strip()
        vals["recovery"] = raw_recovery or False

        # ── Recovery Period ──────────────────────────────────────
        vals["recovery_period_value"] = self._safe_int(
            data.get("recovery_period_value"), default=0
        )
        vals["recovery_period_unit"] = (
            data.get("recovery_period_unit") or False
        )

        # ── Risk Level & Risks ───────────────────────────────────
        vals["risk_level"] = data.get("risk_level") or False
        raw_risks = (data.get("risks") or "").strip()
        vals["risks"] = raw_risks or False

        return vals
