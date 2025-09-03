# models/service_catalog.py

from odoo import models, fields, api


class ServiceCatalog(models.Model):
    _name = 'service.catalog'
    _description = 'Service Catalog'
    _order = 'service_type_id, sequence, name'
    _inherit = ['sequence.helper']

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Service Code', readonly=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=10)

    # ИСПРАВЛЕНО: правильная связь с service.type вместо category
    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)
    category_id = fields.Many2one('service.category', string='Category',
                                  related='service_type_id.category_id', store=True, readonly=True)

    description = fields.Text(string='Description')

    # УПРОЩЕНО: только базовая информация, основное в service.type
    complexity_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Complexity Level', default='medium')

    # Дополнительные характеристики конкретной услуги
    base_cost = fields.Monetary(string='Base Cost', currency_field='currency_id',
                                help='Base cost for this specific service variant')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Специфичные для каталога поля
    vendor = fields.Char(string='Vendor/Brand')
    model_version = fields.Char(string='Model/Version')

    # Technical specifications
    specifications = fields.Text(string='Technical Specifications')

    # Support details - наследуется от service.type, но можно переопределить
    support_hours = fields.Float(string='Support Hours Required',
                                 help='Hours required to support this service per unit')

    active = fields.Boolean(string='Active', default=True)

    # Relations
    client_service_ids = fields.One2many('client.service', 'service_catalog_id', string='Client Services')

    # Statistics
    client_count = fields.Integer(string='Clients', compute='_compute_stats')
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_stats')

    @api.depends('client_service_ids.status', 'client_service_ids.quantity')
    def _compute_stats(self):
        for catalog in self:
            active_services = catalog.client_service_ids.filtered(lambda s: s.status == 'active')
            catalog.client_count = len(active_services.mapped('client_id'))
            catalog.total_quantity = sum(active_services.mapped('quantity'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.catalog.code')
        return super().create(vals_list)