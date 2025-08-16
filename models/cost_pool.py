from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CostPool(models.Model):
    _name = 'cost.pool'
    _description = 'Cost Pool'
    _rec_name = 'name'

    name = fields.Char(string='Pool Name', required=True)
    description = fields.Text(string='Description')
    pool_type = fields.Selection([
        ('direct', 'Direct Costs'),
        ('indirect', 'Indirect Costs'),
        ('admin', 'Administrative Costs')
    ], string='Pool Type', default='indirect', required=True)

    active = fields.Boolean(string='Active', default=True)

    # Employee allocations
    allocation_ids = fields.One2many('cost.pool.allocation', 'pool_id', string='Employee Allocations')

    # Totals
    total_monthly_cost = fields.Float(string='Total Monthly Cost', compute='_compute_total_cost', store=True)

    # Related driver
    driver_id = fields.One2many('cost.driver', 'pool_id', string='Cost Driver')

    @api.depends('allocation_ids.monthly_cost')
    def _compute_total_cost(self):
        for pool in self:
            pool.total_monthly_cost = sum(pool.allocation_ids.mapped('monthly_cost'))


class CostPoolAllocation(models.Model):
    _name = 'cost.pool.allocation'
    _description = 'Cost Pool Employee Allocation'

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True, ondelete='cascade')
    employee_cost_id = fields.Many2one('cost.employee', string='Employee', required=True)
    percentage = fields.Float(string='Allocation %', required=True, default=100.0)
    monthly_cost = fields.Float(string='Monthly Cost', compute='_compute_monthly_cost', store=True)

    @api.depends('employee_cost_id.monthly_total_cost', 'percentage')
    def _compute_monthly_cost(self):
        for allocation in self:
            if allocation.employee_cost_id and allocation.percentage:
                allocation.monthly_cost = allocation.employee_cost_id.monthly_total_cost * (allocation.percentage / 100)
            else:
                allocation.monthly_cost = 0.0

    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise ValidationError("Percentage must be between 0 and 100.")