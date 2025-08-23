from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CostAllocationSettings(models.TransientModel):
    _name = 'cost.allocation.settings'
    _description = 'Cost Allocation Settings'
    _inherit = 'res.config.settings'

    # Administrative costs configuration
    admin_cost_percentage = fields.Float(
        string='Administrative Costs Percentage',
        default=15.0,
        config_parameter='cost_allocation.admin_cost_percentage',
        default_model='cost.allocation.settings',
        help="Percentage of direct+indirect costs allocated as administrative costs"
    )

    admin_allocation_method = fields.Selection([
        ('percentage', 'Percentage of Direct+Indirect'),
        ('pool_based', 'Based on Admin Cost Pools'),
        ('fixed', 'Fixed Amount per Service')
    ], string='Admin Allocation Method',
        default='percentage',
        config_parameter='cost_allocation.admin_allocation_method',
        default_model='cost.allocation.settings',
        help="Method to allocate administrative costs")

    # Overhead allocation
    overhead_allocation_method = fields.Selection([
        ('proportional', 'Proportional to Direct Costs'),
        ('equal', 'Equal Distribution'),
        ('driver_based', 'Cost Driver Based')
    ], string='Overhead Allocation Method',
        default='proportional',
        config_parameter='cost_allocation.overhead_allocation_method',
        default_model='cost.allocation.settings')

    # Default working parameters
    default_working_hours_month = fields.Float(
        string='Default Working Hours per Month',
        default=176.0,
        config_parameter='cost_allocation.default_working_hours_month',
        default_model='cost.allocation.settings',
        help="Default working hours per month for cost calculations"
    )

    default_working_days_month = fields.Float(
        string='Default Working Days per Month',
        default=22.0,
        config_parameter='cost_allocation.default_working_days_month',
        default_model='cost.allocation.settings',
        help="Default working days per month for cost calculations"
    )

    # Working hours calculation method - ДОБАВЛЕНО
    working_hours_method = fields.Selection([
        ('dynamic', 'Dynamic (Calendar-based)'),
        ('fixed', 'Fixed (Manual Override)')
    ], string='Working Hours Method',
        default='dynamic',
        config_parameter='cost_allocation.working_hours_method',
        default_model='cost.allocation.settings',
        help="Method for calculating working hours")

    # Employee utilization rate - ДОБАВЛЕНО
    utilization_rate = fields.Float(
        string='Employee Utilization Rate',
        default=75.0,
        config_parameter='cost_allocation.utilization_rate',
        default_model='cost.allocation.settings',
        help="Expected utilization rate for capacity planning (percentage)"
    )

    # Code generation
    auto_generate_codes = fields.Boolean(
        string='Auto-generate Codes',
        default=True,
        config_parameter='cost_allocation.auto_generate_codes',
        default_model='cost.allocation.settings',
        help="Automatically generate codes for new records"
    )

    @api.constrains('admin_cost_percentage')
    def _check_admin_percentage(self):
        for record in self:
            if record.admin_cost_percentage < 0 or record.admin_cost_percentage > 100:
                raise ValidationError("Administrative cost percentage must be between 0 and 100")

    @api.constrains('utilization_rate')
    def _check_utilization_rate(self):
        for record in self:
            if record.utilization_rate < 0 or record.utilization_rate > 100:
                raise ValidationError("Utilization rate must be between 0 and 100")

    @api.constrains('default_working_hours_month', 'default_working_days_month')
    def _check_working_parameters(self):
        for record in self:
            if record.default_working_hours_month <= 0:
                raise ValidationError("Working hours per month must be positive")
            if record.default_working_days_month <= 0:
                raise ValidationError("Working days per month must be positive")