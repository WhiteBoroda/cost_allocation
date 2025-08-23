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
        help="Percentage of direct+indirect costs allocated as administrative costs"
    )

    admin_allocation_method = fields.Selection([
        ('percentage', 'Percentage of Direct+Indirect'),
        ('pool_based', 'Based on Admin Cost Pools'),
        ('fixed', 'Fixed Amount per Service')
    ], string='Admin Allocation Method', default='percentage',
        help="Method to allocate administrative costs")

    # Overhead allocation
    overhead_allocation_method = fields.Selection([
        ('proportional', 'Proportional to Direct Costs'),
        ('equal', 'Equal Distribution'),
        ('driver_based', 'Cost Driver Based')
    ], string='Overhead Allocation Method', default='proportional')

    # Default working parameters
    default_working_hours_month = fields.Float(
        string='Default Working Hours per Month',
        default=176.0,
        help="Default working hours per month for cost calculations"
    )

    default_working_days_month = fields.Float(
        string='Default Working Days per Month',
        default=22.0,
        help="Default working days per month for cost calculations"
    )

    # Working hours calculation method - ДОБАВЛЕНО
    working_hours_method = fields.Selection([
        ('dynamic', 'Dynamic (Calendar-based)'),
        ('fixed', 'Fixed (Manual Override)')
    ], string='Working Hours Method', default='dynamic',
        help="Method for calculating working hours")

    # Employee utilization rate - ДОБАВЛЕНО
    utilization_rate = fields.Float(
        string='Employee Utilization Rate',
        default=75.0,
        help="Expected utilization rate for capacity planning (percentage)"
    )

    # Code generation
    auto_generate_codes = fields.Boolean(
        string='Auto-generate Codes',
        default=True,
        help="Automatically generate codes for new records"
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()

        res.update(
            admin_cost_percentage=float(ICPSudo.get_param('cost_allocation.admin_cost_percentage', 15.0)),
            admin_allocation_method=ICPSudo.get_param('cost_allocation.admin_allocation_method', 'percentage'),
            overhead_allocation_method=ICPSudo.get_param('cost_allocation.overhead_allocation_method', 'proportional'),
            default_working_hours_month=float(ICPSudo.get_param('cost_allocation.default_working_hours_month', 176.0)),
            default_working_days_month=float(ICPSudo.get_param('cost_allocation.default_working_days_month', 22.0)),
            working_hours_method=ICPSudo.get_param('cost_allocation.working_hours_method', 'dynamic'),
            utilization_rate=float(ICPSudo.get_param('cost_allocation.utilization_rate', 75.0)),
            auto_generate_codes=ICPSudo.get_param('cost_allocation.auto_generate_codes', 'True') == 'True',
        )
        return res

    def set_values(self):
        super().set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()

        ICPSudo.set_param('cost_allocation.admin_cost_percentage', self.admin_cost_percentage)
        ICPSudo.set_param('cost_allocation.admin_allocation_method', self.admin_allocation_method)
        ICPSudo.set_param('cost_allocation.overhead_allocation_method', self.overhead_allocation_method)
        ICPSudo.set_param('cost_allocation.default_working_hours_month', self.default_working_hours_month)
        ICPSudo.set_param('cost_allocation.default_working_days_month', self.default_working_days_month)
        ICPSudo.set_param('cost_allocation.working_hours_method', self.working_hours_method)
        ICPSudo.set_param('cost_allocation.utilization_rate', self.utilization_rate / 100.0)  # Store as decimal
        ICPSudo.set_param('cost_allocation.auto_generate_codes', str(self.auto_generate_codes))

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