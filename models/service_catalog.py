# models/service_catalog.py

from odoo import models, fields, api


class ServiceCatalog(models.Model):
    _name = 'service.catalog'
    _description = 'Service Catalog with ABC Costing'
    _order = 'service_type_id, sequence, name'
    _inherit = ['sequence.helper']

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Service Code', readonly=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=10)

    # Service type relation
    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)
    category_id = fields.Many2one('service.category', string='Category',
                                  related='service_type_id.category_id', store=True, readonly=True)

    description = fields.Text(string='Description')

    # Complexity and effort characteristics
    complexity_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Complexity Level', default='medium')

    # КЛЮЧЕВОЕ ПОЛЕ: сколько часов нужно на одну единицу услуги
    support_hours_per_unit = fields.Float(string='Support Hours per Unit', default=1.0,
                                          help='Hours required to deliver one unit of this service')

    # ABC COSTING: base_cost теперь computed из затрат сотрудников
    base_cost = fields.Monetary(string='Base Cost per Unit', currency_field='currency_id',
                                compute='_compute_base_cost', store=True,
                                help='Computed from employee costs and support hours required')

    # Manual override если нужно
    manual_base_cost = fields.Monetary(string='Manual Base Cost Override', currency_field='currency_id',
                                       help='Override computed base cost with manual value')
    use_manual_cost = fields.Boolean(string='Use Manual Cost', default=False,
                                     help='Use manual cost instead of computed cost')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Pricing with markup
    markup_percentage = fields.Float(string='Markup %', default=20.0,
                                     help='Markup percentage over base cost')
    sales_price = fields.Monetary(string='Sales Price per Unit', currency_field='currency_id',
                                  compute='_compute_sales_price', store=True)

    # Product/vendor specifics
    vendor = fields.Char(string='Vendor/Brand')
    model_version = fields.Char(string='Model/Version')
    product_category = fields.Char(string='Product Category')
    additional_info = fields.Text(string='Additional Information')
    specifications = fields.Text(string='Technical Specifications')

    active = fields.Boolean(string='Active', default=True)

    # Relations
    client_service_ids = fields.One2many('client.service', 'service_catalog_id', string='Client Services')

    # Statistics
    client_count = fields.Integer(string='Clients', compute='_compute_client_stats', store=True)
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_client_stats', store=True)
    average_quantity_per_client = fields.Float(string='Avg Quantity per Client',
                                               compute='_compute_client_analysis')

    # ==================== COMPUTED METHODS - ABC COSTING ====================

    @api.depends('service_type_id.default_responsible_ids', 'support_hours_per_unit', 'use_manual_cost',
                 'manual_base_cost')
    def _compute_base_cost(self):
        """Compute base cost from employee costs and support hours"""
        for catalog in self:
            if catalog.use_manual_cost and catalog.manual_base_cost:
                catalog.base_cost = catalog.manual_base_cost
                continue

            if not catalog.service_type_id or not catalog.service_type_id.default_responsible_ids:
                catalog.base_cost = 0.0
                continue

            # Получить затраты сотрудников ответственных за этот тип услуг
            employees = catalog.service_type_id.default_responsible_ids
            employee_costs = self.env['cost.employee'].search([
                ('employee_id', 'in', employees.ids),
                ('active', '=', True)
            ])

            if not employee_costs:
                catalog.base_cost = 0.0
                continue

            # Рассчитать средневзвешенную стоимость команды
            total_hourly_cost = 0.0
            total_weight = 0.0

            for emp_cost in employee_costs:
                if emp_cost.hourly_cost > 0:
                    # Можно добавить веса на основе компетенций, роли и т.д.
                    # Пока используем равные веса
                    weight = 1.0
                    total_hourly_cost += emp_cost.hourly_cost * weight
                    total_weight += weight

            if total_weight > 0:
                average_hourly_cost = total_hourly_cost / total_weight
                # Base cost = средняя стоимость команды × часы на единицу услуги
                catalog.base_cost = average_hourly_cost * catalog.support_hours_per_unit
            else:
                catalog.base_cost = 0.0

    @api.depends('base_cost', 'markup_percentage')
    def _compute_sales_price(self):
        """Compute sales price with markup"""
        for catalog in self:
            if catalog.base_cost and catalog.markup_percentage:
                catalog.sales_price = catalog.base_cost * (1 + catalog.markup_percentage / 100)
            else:
                catalog.sales_price = catalog.base_cost

    # ==================== EXISTING COMPUTED METHODS ====================

    @api.depends('client_service_ids.status', 'client_service_ids.client_id')
    def _compute_client_stats(self):
        """Compute client statistics for filtering (store=True)"""
        for catalog in self:
            active_services = catalog.client_service_ids.filtered(lambda s: s.status == 'active')
            unique_clients = active_services.mapped('client_id')
            catalog.client_count = len(unique_clients)
            catalog.total_quantity = sum(active_services.mapped('quantity'))

    @api.depends('client_service_ids.status', 'client_service_ids.quantity', 'client_count', 'total_quantity')
    def _compute_client_analysis(self):
        """Compute analysis for display (without store)"""
        for catalog in self:
            catalog.average_quantity_per_client = (
                catalog.total_quantity / catalog.client_count if catalog.client_count > 0 else 0
            )

    # ==================== UTILITY METHODS ====================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.catalog.code')
            # Set default support hours if not provided
            if not vals.get('support_hours_per_unit'):
                vals['support_hours_per_unit'] = 1.0
        return super().create(vals_list)

    def action_view_clients(self):
        """View clients using this catalog service"""
        self.ensure_one()
        client_ids = self.client_service_ids.filtered(lambda s: s.status == 'active').mapped('client_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': f'Clients using {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', client_ids), ('is_company', '=', True)],
            'context': {'create': False},
        }

    def action_view_cost_breakdown(self):
        """View detailed cost breakdown for this service"""
        self.ensure_one()

        if not self.service_type_id.default_responsible_ids:
            from odoo.exceptions import UserError
            raise UserError(f"No responsible employees defined for service type '{self.service_type_id.name}'. "
                            f"Please configure responsible team first.")

        # Open wizard showing cost breakdown
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cost Breakdown: {self.name}',
            'res_model': 'service.cost.breakdown.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_service_catalog_id': self.id,
            }
        }

    def get_cost_breakdown_data(self):
        """Get detailed cost breakdown data"""
        self.ensure_one()

        breakdown = {
            'service_name': self.name,
            'support_hours_per_unit': self.support_hours_per_unit,
            'base_cost': self.base_cost,
            'sales_price': self.sales_price,
            'markup_percentage': self.markup_percentage,
            'employee_costs': []
        }

        if self.service_type_id.default_responsible_ids:
            employees = self.service_type_id.default_responsible_ids
            employee_costs = self.env['cost.employee'].search([
                ('employee_id', 'in', employees.ids),
                ('active', '=', True)
            ])

            for emp_cost in employee_costs:
                breakdown['employee_costs'].append({
                    'employee_name': emp_cost.employee_id.name,
                    'monthly_cost': emp_cost.monthly_total_cost,
                    'hourly_cost': emp_cost.hourly_cost,
                    'cost_per_service_unit': emp_cost.hourly_cost * self.support_hours_per_unit
                })

        return breakdown