# models/service_type.py

from odoo import models, fields, api


class ServiceType(models.Model):
    _name = 'service.type'
    _description = 'Service Type'
    _order = 'category_id, sequence, name'
    _inherit = ['sequence.helper']

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Code', readonly=True, copy=False)
    category_id = fields.Many2one('service.category', string='Category', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    # ОСНОВНЫЕ поля pricing и billing - здесь определяется тип услуги
    service_type = fields.Selection([
        ('workstation', 'Workstation'),
        ('server', 'Server'),
        ('printer', 'Printer'),
        ('network', 'Network Equipment'),
        ('software', 'Software License'),
        ('user', 'User Support'),
        ('project', 'Project Work'),
        ('consulting', 'Consulting'),
        ('other', 'Other')
    ], string='Service Classification', required=True, default='other',
       help='Classification for cost driver mapping')

    # Unit of measure - связь со справочником
    unit_id = fields.Many2one('unit.of.measure', string='Unit of Measure', required=True)

    # Базовое ценообразование на уровне типа
    base_price = fields.Monetary(string='Base Price per Unit', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # SLA на уровне типа услуги (базовые значения)
    response_time = fields.Float(string='Base Response Time (hours)', default=24.0,
                                 help='Base response time - actual SLA determined by client support level')
    resolution_time = fields.Float(string='Base Resolution Time (hours)', default=72.0,
                                   help='Base resolution time - actual SLA determined by client support level')
    availability_sla = fields.Float(string='Availability SLA (%)', default=99.0)

    # Workload characteristics
    base_workload_factor = fields.Float(string='Base Workload Factor', default=1.0,
                                        help='Base workload multiplier for this service type')
    requires_onsite = fields.Boolean(string='Requires On-site Support', default=False)

    # Responsible employees for this service type
    default_responsible_ids = fields.Many2many('hr.employee',
                                               'service_type_employee_rel',
                                               'service_type_id', 'employee_id',
                                               string='Default Responsible Team')
    primary_responsible_id = fields.Many2one('hr.employee', string='Primary Responsible')

    # Relations
    catalog_ids = fields.One2many('service.catalog', 'service_type_id', string='Catalog Items')
    client_service_ids = fields.One2many('client.service', 'service_type_id', string='Client Services')

    # Statistics
    catalog_count = fields.Integer(string='Catalog Items', compute='_compute_counts')
    active_services_count = fields.Integer(string='Active Services', compute='_compute_counts')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('catalog_ids', 'client_service_ids.status')
    def _compute_counts(self):
        for service_type in self:
            service_type.catalog_count = len(service_type.catalog_ids)
            service_type.active_services_count = len(
                service_type.client_service_ids.filtered(lambda s: s.status == 'active')
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.type.code')
        return super().create(vals_list)