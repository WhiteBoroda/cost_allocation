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

    # ИСПРАВЛЕНО: используем справочник вместо захардкоженных значений
    service_type = fields.Selection(
        selection='_get_service_types',
        string='Service Classification',
        default='support',
        required=True,
        help='Service classification from configurable dictionary'
    )

    # Relations
    service_type_ids = fields.One2many('service.type', 'category_id', string='Service Types')
    cost_pool_id = fields.Many2one('cost.pool', string='Related Cost Pool')

    # Responsible employees for this category
    default_responsible_ids = fields.Many2many('hr.employee',
                                               'category_employee_rel',
                                               'category_id', 'employee_id',
                                               string='Default Responsible Team')
    primary_responsible_id = fields.Many2one('hr.employee', string='Primary Responsible')

    # Statistics
    service_type_count = fields.Integer(string='Service Types', compute='_compute_counts')
    active_services_count = fields.Integer(string='Active Services', compute='_compute_counts')

    active = fields.Boolean(string='Active', default=True)

    @api.model
    def _get_service_types(self):
        """Получаем типы из справочника с fallback"""
        try:
            return self.env['service.classification'].get_selection_list()
        except:
            # Fallback на время установки модуля
            return [
                ('workstation', 'Workstation'),
                ('server', 'Server'),
                ('printer', 'Printer'),
                ('network', 'Network Equipment'),
                ('software', 'Software License'),
                ('user', 'User Support'),
                ('project', 'Project Work'),
                ('consulting', 'Consulting'),
                ('hardware', 'Hardware'),
                ('support', 'Support'),
                ('other', 'Other')
            ]

    @api.depends('service_type_ids')
    def _compute_counts(self):
        for category in self:
            category.service_type_count = len(category.service_type_ids)

            # Считаем активные сервисы через service.type
            active_count = 0
            for service_type in category.service_type_ids:
                active_count += len(service_type.client_service_ids.filtered(lambda s: s.status == 'active'))
            category.active_services_count = active_count

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.category.code')
        return super().create(vals_list)