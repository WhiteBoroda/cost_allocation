# models/cost_driver_category.py
from odoo import models, fields

class CostDriverCategory(models.Model):
    _name = 'cost.driver.category'
    _description = 'Cost Driver Category'
    _order = 'sequence, name'

    name = fields.Char('Category Name', required=True)
    code = fields.Char('Code')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean(default=True)
    description = fields.Text('Description')