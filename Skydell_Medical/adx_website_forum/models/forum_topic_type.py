# -*- coding: utf-8 -*-
from odoo import models, fields


class ForumTopicType(models.Model):
    _name = "forum.topic.type"
    _description = "Topic Type"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    description = fields.Html(string="Description")
