from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EmployeeCost(models.Model):
    _name = 'cost.employee'
    _description = 'Employee Cost Configuration'
    _rec_name = 'employee_id'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: наследование для автогенерации кодов

    # ДОБАВЛЕНО: поле кода
    code = fields.Char(string='Employee Cost Code', readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)

    # Основные поля - зарплата уже включает все налоги
    monthly_salary = fields.Float(string='Monthly Cost (with taxes)', compute='_compute_payroll_data', store=True,
                                  help='Total monthly cost including all taxes and contributions')
    monthly_benefits = fields.Float(string='Monthly Benefits', compute='_compute_payroll_data', store=True,
                                    help='Additional benefits (health insurance, etc.)')

    # Manual overrides
    manual_salary = fields.Float(string='Manual Salary Override',
                                 help='Override total monthly cost (including taxes)')
    manual_benefits = fields.Float(string='Manual Benefits Override')
    use_manual = fields.Boolean(string='Use Manual Values', default=False)

    # Working hours
    monthly_hours = fields.Float(string='Monthly Working Hours', default=168.0, required=True,
                                 help='Standard: 21 working days × 8 hours = 168 hours')

    # Calculated fields
    hourly_cost = fields.Float(string='Hourly Cost', compute='_compute_hourly_cost', store=True)
    monthly_total_cost = fields.Float(string='Monthly Total Cost', compute='_compute_monthly_total_cost', store=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)

    # Last update tracking
    last_payroll_period = fields.Date(string='Last Update', compute='_compute_payroll_data', store=True)

    @api.depends('employee_id', 'use_manual', 'manual_salary', 'manual_benefits')
    def _compute_payroll_data(self):
        """Get salary data from employee contract"""
        for record in self:
            if record.use_manual:
                record.monthly_salary = record.manual_salary
                record.monthly_benefits = record.manual_benefits
                record.last_payroll_period = fields.Date.today()
            elif record.employee_id:
                record._get_contract_data()
            else:
                record.monthly_salary = 0
                record.monthly_benefits = 0
                record.last_payroll_period = False

    def _get_contract_data(self):
        """Get data from employee contract - salary should already include taxes"""
        contract = None

        # Try different ways to get contract
        if hasattr(self.employee_id, 'contract_id') and self.employee_id.contract_id:
            contract = self.employee_id.contract_id
        elif hasattr(self.employee_id, 'contract_ids') and self.employee_id.contract_ids:
            # Get current contract
            contracts = self.employee_id.contract_ids.filtered(lambda c: c.state == 'open')
            contract = contracts[0] if contracts else self.employee_id.contract_ids[0]

        if contract and hasattr(contract, 'wage'):
            # В контракте указана полная стоимость сотрудника (зарплата + налоги)
            self.monthly_salary = contract.wage
            self.monthly_benefits = 0  # Можно добавить из других полей контракта
            self.last_payroll_period = fields.Date.today()
        else:
            # No contract found
            self.monthly_salary = 0
            self.monthly_benefits = 0
            self.last_payroll_period = False

    @api.depends('monthly_salary', 'monthly_benefits', 'monthly_hours')
    def _compute_hourly_cost(self):
        """Calculate hourly cost"""
        for record in self:
            if record.monthly_hours > 0:
                total_cost = record.monthly_salary + record.monthly_benefits
                record.hourly_cost = total_cost / record.monthly_hours
            else:
                record.hourly_cost = 0.0

    @api.depends('monthly_salary', 'monthly_benefits')
    def _compute_monthly_total_cost(self):
        """Calculate total monthly cost"""
        for record in self:
            record.monthly_total_cost = record.monthly_salary + record.monthly_benefits

    @api.constrains('monthly_hours')
    def _check_monthly_hours(self):
        for record in self:
            if record.monthly_hours <= 0:
                raise ValidationError('Monthly hours must be greater than 0')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ДОБАВЛЕНО: автогенерация кода
            if not vals.get('code'):
                vals['code'] = self._generate_code('cost.employee.code')
        return super().create(vals_list)

    def action_update_from_contract(self):
        """Manual action to update from contract"""
        self.ensure_one()
        self._compute_payroll_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Updated data for {self.employee_id.name}',
                'type': 'success',
            }
        }

    @api.model
    def update_all_from_contracts(self):
        """Cron job method to update all employee costs"""
        employees = self.search([('use_manual', '=', False)])
        for emp in employees:
            emp._compute_payroll_data()

    _sql_constraints = [
        ('unique_employee', 'unique(employee_id)', 'Employee cost configuration must be unique!')
    ]