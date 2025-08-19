from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EmployeeCost(models.Model):
    _name = 'cost.employee'
    _description = 'Employee Cost Configuration'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)

    # Auto-calculated from payroll
    monthly_salary = fields.Float(string='Monthly Salary', compute='_compute_payroll_data', store=True)
    monthly_taxes = fields.Float(string='Monthly Taxes', compute='_compute_payroll_data', store=True)
    monthly_benefits = fields.Float(string='Monthly Benefits', compute='_compute_payroll_data', store=True)

    # Manual overrides
    manual_salary = fields.Float(string='Manual Salary Override')
    manual_taxes = fields.Float(string='Manual Taxes Override')
    manual_benefits = fields.Float(string='Manual Benefits Override')
    use_manual = fields.Boolean(string='Use Manual Values', default=False)

    # Company-based Dія.City status (computed from employee's company)
    is_diia_city = fields.Boolean(string='Dія.City Resident', compute='_compute_diia_city_status', store=False,
                                  help='Company is Dія.City resident: 5% income tax + 5% military tax + 22% ESV from minimum wage')

    # ДОБАВЛЕНО НЕДОСТАЮЩЕЕ ПОЛЕ:
    is_diia_city_own = fields.Boolean(
        string='Dія.City Resident (Own)',
        default=False,
        help='Use Dія.City tax rates: 5% income tax + 5% military tax + 22% ESV from minimum wage'
    )

    minimum_wage = fields.Float(string='Minimum Wage for ESV', default=7723.0,
                                help='Current minimum wage in Ukraine for ESV calculation')

    monthly_hours = fields.Float(string='Monthly Working Hours', default=168.0, required=True)
    hourly_cost = fields.Float(string='Hourly Cost', compute='_compute_hourly_cost', store=True)

    # Total cost field needed by cost pools
    monthly_total_cost = fields.Float(string='Monthly Total Cost', compute='_compute_monthly_total_cost', store=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)

    # Last payroll period for calculation
    last_payroll_period = fields.Date(string='Last Payroll Period', compute='_compute_payroll_data', store=True)

    # ИСПРАВЛЕН @api.depends:
    @api.depends('employee_id', 'is_diia_city_own')
    def _compute_diia_city_status(self):
        """Get Dія.City status from manual setting or employee's company"""
        for record in self:
            # Проверяем есть ли поле в company (если установлен внешний модуль)
            if (record.employee_id and
                    record.employee_id.company_id and
                    hasattr(record.employee_id.company_id, 'is_diia_city_resident')):
                record.is_diia_city = record.employee_id.company_id.is_diia_city_resident
            else:
                # Используем ручную настройку
                record.is_diia_city = record.is_diia_city_own

    # ИСПРАВЛЕН @api.depends:
    @api.depends('employee_id', 'use_manual', 'manual_salary', 'manual_taxes', 'manual_benefits',
                 'minimum_wage', 'is_diia_city_own')
    def _compute_payroll_data(self):
        for record in self:
            if record.use_manual:
                record.monthly_salary = record.manual_salary
                record.monthly_taxes = record.manual_taxes
                record.monthly_benefits = record.manual_benefits
                record.last_payroll_period = False
            elif record.employee_id:
                record._fallback_to_contract()
            else:
                record.monthly_salary = 0
                record.monthly_taxes = 0
                record.monthly_benefits = 0
                record.last_payroll_period = False

    def _fallback_to_contract(self):
        """Get data from employee contract with Dія.City tax calculation"""
        contract = None

        # Try different ways to get contract
        if hasattr(self.employee_id, 'contract_id') and self.employee_id.contract_id:
            contract = self.employee_id.contract_id
        elif hasattr(self.employee_id, 'contract_ids') and self.employee_id.contract_ids:
            # Get current contract
            contracts = self.employee_id.contract_ids.filtered(lambda c: c.state == 'open')
            contract = contracts[0] if contracts else self.employee_id.contract_ids[0]

        if contract and hasattr(contract, 'wage'):
            wage = contract.wage
            self.monthly_salary = wage

            # ИСПРАВЛЕНО: Используем computed field вместо прямого обращения к company
            is_diia_city = self.is_diia_city

            if is_diia_city:
                # Dія.City tax calculation
                income_tax = wage * 0.05  # 5% income tax
                military_tax = wage * 0.05  # 5% military tax
                esv_base = self.minimum_wage or 7723.0  # ESV from minimum wage
                esv = esv_base * 0.22  # 22% ESV from minimum wage

                self.monthly_taxes = income_tax + military_tax + esv
            else:
                # Standard Ukrainian tax calculation (22% ESV from full wage)
                self.monthly_taxes = wage * 0.22

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

    @api.depends('monthly_salary', 'monthly_taxes', 'monthly_benefits')
    def _compute_monthly_total_cost(self):
        for record in self:
            record.monthly_total_cost = record.monthly_salary + record.monthly_taxes + record.monthly_benefits

    @api.constrains('monthly_hours')
    def _check_monthly_hours(self):
        for record in self:
            if record.monthly_hours <= 0:
                raise ValidationError('Monthly hours must be greater than 0')

    # ИСПРАВЛЕН @api.constrains:
    @api.constrains('minimum_wage', 'is_diia_city_own')
    def _check_minimum_wage(self):
        for record in self:
            # Используем computed field вместо прямого обращения к company
            if record.is_diia_city and record.minimum_wage <= 0:
                raise ValidationError('Minimum wage must be greater than 0 for Dія.City residents')

    def action_update_from_payroll(self):
        """Manual action to update from contract"""
        self._compute_payroll_data()
        return True

    @api.model
    def get_default_minimum_wage(self):
        """Get current minimum wage setting from company"""
        # Can be extended to get from company settings
        return 7723.0  # Current minimum wage in Ukraine as of 2024

    _sql_constraints = [
        ('unique_employee', 'unique(employee_id)', 'Employee cost configuration must be unique!')
    ]