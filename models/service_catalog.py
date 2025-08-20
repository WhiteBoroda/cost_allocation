from odoo import models, fields, api


class ServiceCategory(models.Model):
    _name = 'service.category'
    _description = 'Service Category'
    _order = 'sequence, name'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: наследование для автогенерации кодов

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', readonly=True, copy=False)  # ИЗМЕНЕНО: readonly, copy=False
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    service_type = fields.Selection([
        ('hardware', 'Hardware'),
        ('saas', 'SaaS'),
        ('iaas', 'IaaS'),
        ('support', 'Support')
    ], string='Service Type', default='support')

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

    @api.depends('service_ids')
    def _compute_counts(self):
        for category in self:
            category.service_type_count = len(category.service_ids)
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


class ServiceCatalog(models.Model):
    _name = 'service.catalog'
    _description = 'Service Catalog'
    _order = 'category_id, sequence, name'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: наследование для автогенерации кодов

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Service Code', readonly=True, copy=False)  # ИЗМЕНЕНО: readonly, copy=False
    sequence = fields.Integer(string='Sequence', default=10)

    category_id = fields.Many2one('service.category', string='Category', required=True)
    service_type = fields.Selection(related='category_id.service_type', store=True)

    description = fields.Text(string='Description')

    # Pricing and billing
    unit_of_measure = fields.Selection([
        ('unit', 'Per Unit'),
        ('hour', 'Per Hour'),
        ('month', 'Per Month'),
        ('user', 'Per User'),
        ('license', 'Per License'),
        ('gb', 'Per GB')
    ], string='Unit of Measure', default='unit', required=True)

    complexity_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Complexity Level', default='medium')

    base_cost = fields.Float(string='Base Cost', help='Internal cost for this service')
    markup_percent = fields.Float(string='Markup %', default=20.0, help='Markup percentage over base cost')
    sales_price = fields.Float(string='Sales Price', compute='_compute_sales_price', store=True)

    # Service details
    support_hours = fields.Float(string='Support Hours', default=0.0,
                                 help='Estimated support hours per unit')
    sla_response_time = fields.Float(string='SLA Response Time (hours)', default=24.0)

    property_account_income_id = fields.Many2one(
        'account.account',
        string='Income Account',
        domain="[('account_type', '=', 'income'), ('company_id', '=', current_company_id)]",
        help="Account used for income when invoicing this service"
    )

    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)

    active = fields.Boolean(string='Active', default=True)

    @api.depends('base_cost', 'markup_percent')
    def _compute_sales_price(self):
        for service in self:
            if service.base_cost and service.markup_percent:
                service.sales_price = service.base_cost * (1 + service.markup_percent / 100)
            else:
                service.sales_price = service.base_cost

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Service code must be unique!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.catalog.code')
            if not vals.get('property_account_income_id'):
                # Try to find a default income account
                income_account = self.env['account.account'].search([
                    ('account_type', '=', 'income'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if income_account:
                    vals['property_account_income_id'] = income_account.id

        return super().create(vals_list)