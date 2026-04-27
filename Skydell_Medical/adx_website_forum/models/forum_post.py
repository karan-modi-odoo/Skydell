# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time, date
from odoo import models, fields, api

# Engagement score weights — upvotes carry most weight per unit (5 > 3 > 1)
_WEIGHT_UPVOTES = 5
_WEIGHT_REPLIES = 3
_WEIGHT_VIEWS = 1


class ForumPost(models.Model):
    _inherit = "forum.post"

    topic_type_id = fields.Many2one(
        "forum.topic.type", string="Topic Type", tracking=True
    )
    compliance_confirmation = fields.Boolean(
        string="No Patient Data Confirmed", default=False
    )
    is_clinical_insight = fields.Boolean(
        string="Clinical Insight of the Week",
        default=False,
        tracking=True,
        index=True,
    )
    # ── Procedure & Product Details ───────────────────────────────
    is_procedure_post = fields.Boolean(
        string="Is Procedure Post",
        default=False,
    )

    procedure_type_id = fields.Many2one(
        "procedure.type",
        string="Procedure Type",
    )
    product_used_id = fields.Many2one(
        "product.template",
        string="Product Used",
    )
    date_performed = fields.Date(string="Date Performed")
    results = fields.Html(string="Results")
    results_text = fields.Text(
        string="Results (Plain)",
        compute="_compute_results_text",
    )
    # New fields
    specialty_id = fields.Many2one(comodel_name="doctor.specialty", string="Speciality")
    doctor_experience = fields.Integer(
        string="Doctor Experience",
        help="Required experience or qualification of the doctor.",
    )
    duration = fields.Integer(
        string="Duration Value",
        help="Numeric duration of the procedure.",
    )
    duration_unit = fields.Selection(
        [
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
            ("years", "Years"),
        ],
        string="Duration Unit",
        default="hours",
    )
    recovery_period_value = fields.Integer(
        string="Recovery Period Value",
        help="Enter the numeric value for the recovery period (e.g. 2).",
    )
    recovery_period_unit = fields.Selection(
        [
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
            ("years", "Years"),
        ],
        string="Recovery Period Unit",
    )

    recovery = fields.Html(
        string="Recovery",
        help="Recovery details and post-procedure care instructions.",
    )
    risk_level = fields.Selection(
        [
            ("low", "Low Risk"),
            ("medium", "Medium Risk"),
            ("high", "High Risk"),
        ],
        string="Risk Level",
    )
    risks = fields.Html(
        string="Risks",
        help="Potential risks and complications associated " "with this procedure.",
    )

    def _compute_results_text(self):
        import re

        for rec in self:
            if rec.results:
                rec.results_text = re.sub(r"<[^>]+>", "", rec.results or "").strip()
            else:
                rec.results_text = ""

    other_procedure_detail = fields.Char(
        string="Other Procedure Detail",
    )
    upvote_count = fields.Integer(
        string="Upvotes",
        compute="_compute_upvote_downvote_count",
        store=True,
    )
    downvote_count = fields.Integer(
        string="Downvotes",
        compute="_compute_upvote_downvote_count",
        store=True,
    )
    procedure_description = fields.Html(string="Procedure Description")

    @api.depends("vote_ids.vote")
    def _compute_upvote_downvote_count(self):
        for post in self:
            post.upvote_count = len(post.vote_ids.filtered(lambda v: v.vote == "1"))
            post.downvote_count = len(post.vote_ids.filtered(lambda v: v.vote == "-1"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            topic_type_id = vals.get("topic_type_id")
            if topic_type_id and not vals.get("content"):
                topic = self.env["forum.topic.type"].browse(topic_type_id)
                if topic.exists() and topic.description:
                    vals["content"] = topic.description
        return super().create(vals_list)

    def _compute_engagement_score(self):
        """Weighted score: upvotes × 5 + replies × 3 + views × 1."""
        self.ensure_one()
        return (
            self.vote_count * _WEIGHT_UPVOTES
            + self.child_count * _WEIGHT_REPLIES
            + self.views * _WEIGHT_VIEWS
        )

    @api.model
    def _get_week_boundaries(self):
        """Return Monday 00:00 and Sunday 23:59 of
        the current calendar week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return (
            datetime.combine(week_start, time.min),
            datetime.combine(week_end, time.max),
        )

    @api.model
    def _select_clinical_insight_winner(self, start_dt, end_dt):
        """
        Return the highest-scoring active top-level post created this week,
        or an empty recordset if no eligible posts exist.
        """
        candidates = self.search(
            [
                ("parent_id", "=", False),
                ("state", "=", "active"),
                ("create_date", ">=", fields.Datetime.to_string(start_dt)),
                ("create_date", "<=", fields.Datetime.to_string(end_dt)),
            ]
        )
        if not candidates:
            return self.browse()

        winner = max(candidates, key=lambda p: p._compute_engagement_score())
        score = winner._compute_engagement_score()
        return winner if score > 0 else self.browse()

    @api.model
    def send_weekly_pro_digest(self):
        """
        Weekly cron: select this week's Clinical Insight winner,
        update the flag, then send the digest email to all active doctor users.
        """
        start_dt, end_dt = self._get_week_boundaries()
        winner = self._select_clinical_insight_winner(start_dt, end_dt)

        # Clear previous flags, then mark new winner
        prev_flagged = self.search([("is_clinical_insight", "=", True)])
        if prev_flagged:
            prev_flagged.write({"is_clinical_insight": False})
        if winner:
            winner.write({"is_clinical_insight": True})

        all_posts = self.search(
            [
                ("parent_id", "=", False),
                ("state", "=", "active"),
            ]
        )
        if not all_posts and not winner:
            return

        # Batch comment counts for this week — avoids N+1 queries
        comment_data = self._read_group(
            domain=[
                ("parent_id", "in", all_posts.ids),
                ("create_date", ">=", fields.Datetime.to_string(start_dt)),
                ("create_date", "<=", fields.Datetime.to_string(end_dt)),
            ],
            groupby=["parent_id"],
            aggregates=["__count"],
        )
        comment_counts = {post.id: count for post, count in comment_data}

        most_liked_post = (
            max(all_posts, key=lambda p: p.vote_count)
            if any(p.vote_count > 0 for p in all_posts)
            else False
        )

        most_commented_post = False
        max_comments = 0
        for post in all_posts:
            count = comment_counts.get(post.id, 0)
            if count > max_comments:
                max_comments = count
                most_commented_post = post

        template = self.env.ref(
            "adx_website_forum.weekly_digest_email_template",
            raise_if_not_found=False,
        )
        if not template:
            return

        users = self.env["res.users"].search(
            [
                ("partner_id.is_doctor", "=", True),
                ("active", "=", True),
            ]
        )
        if not users:
            return

        ctx = {
            "insight_post": winner,
            "insight_score": (winner._compute_engagement_score() if winner else 0),
            "most_liked_post": most_liked_post,
            "most_liked_likes": (most_liked_post.vote_count if most_liked_post else 0),
            "most_liked_comments": (
                most_liked_post.child_count if most_liked_post else 0
            ),
            "most_commented_post": most_commented_post,
            "most_commented_count": max_comments,
        }

        for user in users:
            email_values = {
                "email_to": user.partner_id.email,
            }
            template.with_context(**ctx).send_mail(
                user.id, email_values=email_values, force_send=True
            )
