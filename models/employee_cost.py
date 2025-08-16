from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EmployeeCost(models.Model):
    _name = 'cost.employee'
    _description = 'Employee Cost Configuration'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)

    # Auto-calculated from payroll
    monthly_salary = fields.Float(string='Monthly Salary', compute='_compute_payroll_data', store=True)
    monthly_taxes = fields.Float(string='Monthly Taxes (ESV)', compute='_compute_payroll_data', store=True)
    monthly_benefits = fields.Float(string='Monthly Benefits', compute='_compute_payroll_data', store=True)

    # Manual overrides
    manual_salary = fields.Float(string='Manual Salary Override')
    manual_taxes = fields.Float(string='Manual Taxes Override')
    manual_benefits = fields.Float(string='Manual Benefits Override')
    use_manual = fields.Boolean(string='Use Manual Values', default=False)

    monthly_hours = fields.Float(string='Monthly Working Hours', default=168.0, required=True)
    hourly_cost = fields.Float(string='Hourly Cost', compute='_compute_hourly_cost', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)

    # Last payroll period for calculation
    last_payroll_period = fields.Date(string='Last Payroll Period', compute='_compute_payroll_data', store=True)

    @api.depends('employee_id', 'use_manual', 'manual_salary', 'manual_taxes', 'manual_benefits')
    def _compute_payroll_data(self):
        for record in self:
            if record.use_manual:
                record.monthly_salary = record.manual_salary
                record.monthly_taxes = record.manual_taxes
                record.monthly_benefits = record.manual_benefits
                record.last_payroll_period = False
            elif record.employee_id:
                # Always use contract data for simplicity and compatibility
                record._fallback_to_contract()
            else:
                record.monthly_salary = 0
                record.monthly_taxes = 0
                record.monthly_benefits = 0
                record.last_payroll_period = False

    def _fallback_to_contract(self):
        """Get data from employee contract"""
        contract = None

        # Try different ways to get contract
        if hasattr(self.employee_id, 'contract_id') and self.employee_id.contract_id:
            contract = self.employee_id.contract_id
        elif hasattr(self.employee_id, 'contract_ids') and self.employee_id.contract_ids:
            # Get current contract
            contracts = self.employee_id.contract_ids.filtered(lambda c: c.state == 'open')
            contract = contracts[0] if contracts else self.employee_id.contract_ids[0]

        if contract and hasattr(contract, 'wage'):
            self.monthly_salary = contract.wage
            # Standard Ukrainian ESV rate is 22%
            self.monthly_taxes = contract.wage * 0.22
            self.monthly_benefits = 0
            self.last_payroll_period = False
        else:
            # No contract found - set zeros
            self.monthly_salary = 0
            self.monthly_taxes = 0
            self.monthly_benefits = 0
            self.last_payroll_period = False

    @api.depends('monthly_salary', 'monthly_taxes', 'monthly_benefits', 'monthly_hours')
    def _compute_hourly_cost(self):
        for record in self:
            if record.monthly_hours > 0:
                total_cost = record.monthly_salary + record.monthly_taxes + record.monthly_benefits
                record.hourly_cost = total_cost / record.monthly_hours
            else:
                record.hourly_cost = 0.0

    @api.constrains('monthly_hours')
    def _check_monthly_hours(self):
        for record in self:
            if record.monthly_hours <= 0:
                raise ValidationError('Monthly hours must be greater than 0')

    def action_update_from_payroll(self):
        """Manual action to update from contract"""
        self._compute_payroll_data()
        return True

    _sql_constraints = [
        ('unique_employee', 'unique(employee_id)', 'Employee cost configuration must be unique!')
    ]