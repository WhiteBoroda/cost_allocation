# models/unit_measure.py
from odoo import models, fields, api


class UnitOfMeasure(models.Model):
    _name = 'unit.of.measure'
    _description = 'Unit of Measure'
    _order = 'category_id, name'
    _rec_name = 'display_name'

    name = fields.Char(string='Unit Name', required=True)
    symbol = fields.Char(string='Symbol', required=True, size=10,
                         help='Short symbol for this unit (e.g., "PC", "Hr", "GB")')

    category_id = fields.Many2one('unit.measure.category', string='Category', required=True)

    # Display name combining name and symbol
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    # For conversion (if needed later)
    ratio = fields.Float(string='Ratio to Base Unit', default=1.0,
                         help='How many of this unit = 1 base unit')

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    @api.depends('name', 'symbol')
    def _compute_display_name(self):
        for unit in self:
            if unit.symbol:
                unit.display_name = f"{unit.name} ({unit.symbol})"
            else:
                unit.display_name = unit.name

    _sql_constraints = [
        ('unique_name_category', 'unique(name, category_id)', 'Unit name must be unique per category!'),
        ('unique_symbol_category', 'unique(symbol, category_id)', 'Unit symbol must be unique per category!'),
    ]


class UnitMeasureCategory(models.Model):
    _name = 'unit.measure.category'
    _description = 'Unit of Measure Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    unit_ids = fields.One2many('unit.of.measure', 'category_id', string='Units')
    unit_count = fields.Integer(string='Unit Count', compute='_compute_unit_count')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('unit_ids')
    def _compute_unit_count(self):
        for category in self:
            category.unit_count = len(category.unit_ids)

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Category name must be unique!'),
    ]