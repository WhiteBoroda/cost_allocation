from odoo import models, fields, api


class ServiceCategory(models.Model):
    _name = 'service.category'
    _description = 'Service Category'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    service_type = fields.Selection([
        ('hardware', 'Hardware'),
        ('saas', 'SaaS'),
        ('iaas', 'IaaS'),
        ('support', 'Support')
    ], string='Service Type', required=True)

    service_ids = fields.One2many('service.catalog', 'category_id', string='Services')
    active = fields.Boolean(string='Active', default=True)


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


class ClientService(models.Model):
    _name = 'client.service'
    _description = 'Client Service Assignment'

    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)])
    service_id = fields.Many2one('service.catalog', string='Service', required=True)

    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    unit_price = fields.Float(string='Unit Price', related='service_id.sales_price')
    total_price = fields.Float(string='Total Price', compute='_compute_total_price', store=True)

    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date(string='End Date')

    # Equipment details for hardware services
    brand = fields.Char(string='Brand')
    model = fields.Char(string='Model')
    serial_number = fields.Char(string='Serial Number')
    location = fields.Char(string='Location')

    # SaaS details
    license_type = fields.Char(string='License Type')
    users_count = fields.Integer(string='Users Count')

    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Active', default=True)

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.quantity * record.unit_price