from odoo import models, fields, api


class ServiceCategory(models.Model):
    _name = 'service.category'
    _description = 'Service Category'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    service_type = fields.Selection([
        ('hardware', 'Hardware'),
        ('saas', 'SaaS'),
        ('iaas', 'IaaS'),
        ('support', 'Support')
    ], string='Service Type', required=True)

    # Relations
    service_ids = fields.One2many('service.catalog', 'category_id', string='Services')
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

    @api.depends('name')
    def _compute_counts(self):
        for category in self:
            category.service_type_count = len(self.env['service.type'].search([('category_id', '=', category.id)]))
            category.active_services_count = len(self.env['client.service'].search([
                ('service_type_id.category_id', '=', category.id),
                ('status', '=', 'active')
            ]))


class ServiceCatalog(models.Model):
    _name = 'service.catalog'
    _description = 'Service Catalog'
    _order = 'category_id, sequence, name'

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Service Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    category_id = fields.Many2one('service.category', string='Category', required=True)
    service_type = fields.Selection(related='category_id.service_type', store=True)

    description = fields.Text(string='Description')
    unit_of_measure = fields.Selection([
        ('unit', 'Per Unit'),
        ('user', 'Per User'),
        ('month', 'Per Month'),
        ('hour', 'Per Hour'),
        ('gb', 'Per GB'),
        ('license', 'Per License')
    ], string='Unit of Measure', default='unit', required=True)

    # Pricing
    base_cost = fields.Float(string='Base Monthly Cost')
    markup_percent = fields.Float(string='Markup %', default=20.0)
    sales_price = fields.Float(string='Sales Price', compute='_compute_sales_price', store=True)

    # Service characteristics
    complexity_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Complexity Level', default='medium')

    support_hours = fields.Float(string='Monthly Support Hours')
    sla_response_time = fields.Integer(string='SLA Response Time (minutes)')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('base_cost', 'markup_percent')
    def _compute_sales_price(self):
        for record in self:
            if record.base_cost and record.markup_percent:
                record.sales_price = record.base_cost * (1 + record.markup_percent / 100)
            else:
                record.sales_price = record.base_cost