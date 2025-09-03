# models/service_category.py

from odoo import models, fields, api


class ServiceCategory(models.Model):
    _name = 'service.category'
    _description = 'Service Category'
    _order = 'sequence, name'
    _inherit = ['sequence.helper']

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', readonly=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    service_type = fields.Selection([
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('support', 'Support'),
        ('consulting', 'Consulting')
    ], string='Service Type', default='support', required=True)

    # Relations - ИСПРАВЛЕНО: правильные связи
    service_type_ids = fields.One2many('service.type', 'category_id', string='Service Types')
    cost_pool_id = fields.Many2one('cost.pool', string='Related Cost Pool')

    # Responsible employees for this category
    default_responsible_ids = fields.Many2many('hr.employee',
                                               'category_employee_rel',
                                               'category_id', 'employee_id',
                                               string='Default Responsible Team')
    primary_responsible_id = fields.Many2one('hr.employee', string='Primary Responsible')

    # Statistics - ИСПРАВЛЕНО: правильные вычисления
    service_type_count = fields.Integer(string='Service Types', compute='_compute_counts')
    active_services_count = fields.Integer(string='Active Services', compute='_compute_counts')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('service_type_ids')
    def _compute_counts(self):
        for category in self:
            category.service_type_count = len(category.service_type_ids)
            category.active_services_count = len(self.env['client.service'].search([
                ('service_type_id.category_id', '=', category.id),
                ('status', '=', 'active')
            ]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.category.code')
        return super().create(vals_list)