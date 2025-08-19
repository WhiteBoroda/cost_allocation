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

    # ИСПРАВЛЕНО: процент как обычное число от 0 до 100, без percentage widget
    percentage = fields.Float(string='Allocation %', required=True, default=100.0,
                              help='Percentage of employee time allocated to this pool (0-100)')
    monthly_cost = fields.Float(string='Monthly Cost', compute='_compute_monthly_cost', store=True)

    @api.depends('employee_cost_id.monthly_total_cost', 'percentage')
    def _compute_monthly_cost(self):
        for allocation in self:
            if allocation.employee_cost_id and allocation.percentage:
                # ИСПРАВЛЕНО: правильное вычисление (percentage уже в формате 0-100)
                allocation.monthly_cost = allocation.employee_cost_id.monthly_total_cost * (allocation.percentage / 100)
            else:
                allocation.monthly_cost = 0.0

    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise ValidationError("Percentage must be between 0 and 100.")

    @api.constrains('employee_cost_id', 'pool_id')
    def _check_unique_employee_pool(self):
        for record in self:
            existing = self.search([
                ('employee_cost_id', '=', record.employee_cost_id.id),
                ('pool_id', '=', record.pool_id.id),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(
                    f"Employee {record.employee_cost_id.employee_id.name} is already allocated to this pool.")

    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.employee_cost_id.employee_id.name} - {record.percentage}%"
            result.append((record.id, name))
        return result