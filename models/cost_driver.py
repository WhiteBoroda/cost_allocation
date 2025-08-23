from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CostDriver(models.Model):
    _name = 'cost.driver'
    _description = 'Cost Driver'
    _rec_name = 'name'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: sequence.helper

    name = fields.Char(string='Driver Name', required=True)
    code = fields.Char(string='Driver Code', readonly=True, copy=False)  # ДОБАВЛЕНО: поле кода
    description = fields.Text(string='Description')

    # ВАЖНО: Поля должны быть здесь!
    driver_category = fields.Char(string='Category', help='E.g.: Hardware, Software, Users, Infrastructure')
    unit_name = fields.Char(string='Unit Name', default='Unit', required=True)  # ДОБАВЛЕНО: недостающее поле!

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True)
    unit_of_measure = fields.Selection([
        ('user', 'Users'),
        ('workstation', 'Workstations'),
        ('printer', 'Printers'),
        ('server', 'Servers'),
        ('gb', 'GB Storage'),
        ('license', 'Licenses'),
        ('hour', 'Hours'),
        ('unit', 'Units')
    ], string='Unit of Measure', default='user', required=True)

    # Cost calculation
    cost_per_unit = fields.Float(string='Cost per Unit', compute='_compute_cost_per_unit', store=True)
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_totals', store=True)

    # Client allocations
    client_driver_ids = fields.One2many('client.cost.driver', 'driver_id', string='Client Allocations')

    # Status
    active = fields.Boolean(string='Active', default=True)

    # Currency
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends('pool_id.total_monthly_cost', 'total_quantity')
    def _compute_cost_per_unit(self):
        for driver in self:
            if driver.total_quantity > 0 and driver.pool_id:
                driver.cost_per_unit = driver.pool_id.total_monthly_cost / driver.total_quantity
            else:
                driver.cost_per_unit = 0.0

    @api.depends('client_driver_ids.quantity')
    def _compute_totals(self):
        for driver in self:
            driver.total_quantity = sum(driver.client_driver_ids.mapped('quantity'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ДОБАВЛЕНО: автогенерация кода
            if not vals.get('code'):
                vals['code'] = self._generate_code('cost.driver.code')
        return super().create(vals_list)

    @api.constrains('cost_per_unit')
    def _check_cost_per_unit(self):
        for record in self:
            if record.cost_per_unit < 0:
                raise ValidationError("Cost per unit cannot be negative")

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Driver code must be unique!')
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