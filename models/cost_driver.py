from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CostDriver(models.Model):
    _name = 'cost.driver'
    _description = 'Cost Driver Configuration'
    _rec_name = 'name'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: наследование для автогенерации кодов

    name = fields.Char(string='Driver Name', required=True)
    code = fields.Char(string='Driver Code', readonly=True, copy=False)  # ИЗМЕНЕНО: readonly, copy=False
    description = fields.Text(string='Description')

    pool_id = fields.Many2one('cost.pool', string='Related Pool', required=True)

    # Гибкое решение - любой тип драйвера
    driver_category = fields.Char(string='Category', help='E.g.: Hardware, Software, Users, Infrastructure')
    unit_name = fields.Char(string='Unit Name', default='Unit', required=True)

    # Client driver values
    client_driver_ids = fields.One2many('client.cost.driver', 'driver_id', string='Client Driver Values')

    # Calculated fields
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_totals', store=True)
    cost_per_unit = fields.Float(string='Cost per Unit', compute='_compute_totals', store=True)

    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)

    # ДОБАВЛЕНО: поле company_id для multi-company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends('client_driver_ids.quantity', 'pool_id.total_monthly_cost')
    def _compute_totals(self):
        for driver in self:
            driver.total_quantity = sum(driver.client_driver_ids.mapped('quantity'))
            if driver.total_quantity > 0 and driver.pool_id.total_monthly_cost > 0:
                driver.cost_per_unit = driver.pool_id.total_monthly_cost / driver.total_quantity
            else:
                driver.cost_per_unit = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ДОБАВЛЕНО: автогенерация кода
            if not vals.get('code'):
                vals['code'] = self._generate_code('cost.driver.code')
        return super().create(vals_list)

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Driver code must be unique!'),
        ('unique_pool', 'unique(pool_id)', 'Each pool can have only one driver!')
    ]


class ClientCostDriver(models.Model):
    _name = 'client.cost.driver'
    _description = 'Client Cost Driver Values'

    driver_id = fields.Many2one('cost.driver', string='Cost Driver', required=True, ondelete='cascade')
    client_id = fields.Many2one('res.partner', string='Client',
                                domain=[('is_company', '=', True)], required=True)
    quantity = fields.Float(string='Quantity', required=True, default=0.0)
    allocated_cost = fields.Float(string='Allocated Cost', compute='_compute_allocated_cost', store=True)

    @api.depends('driver_id.cost_per_unit', 'quantity')
    def _compute_allocated_cost(self):
        for record in self:
            record.allocated_cost = record.driver_id.cost_per_unit * record.quantity

    _sql_constraints = [
        ('unique_driver_client', 'unique(driver_id, client_id)', 'Driver-Client combination must be unique!')
    ]