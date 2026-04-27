from odoo import models, fields


class ProcedureType(models.Model):
    _name = "procedure.type"
    _description = "Procedure Type"
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    description = fields.Html(string="Description")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    specialty_id = fields.Many2one("doctor.specialty", string="Speciality")
    is_other = fields.Boolean(
        string="Is Other",
        default=False,
        help="Mark this as the 'Other' option. "
        "Selecting it on the forum post form will show a free-text field.",
    )
