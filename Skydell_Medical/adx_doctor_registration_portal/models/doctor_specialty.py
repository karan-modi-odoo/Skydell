# -*- coding: utf-8 -*-
from odoo import models, fields


class DoctorSpecialty(models.Model):
    _name = "doctor.specialty"
    _description = "Specialty"

    name = fields.Char(string="Specialty", required=True)
