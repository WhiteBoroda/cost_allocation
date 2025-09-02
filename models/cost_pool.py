from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CostPool(models.Model):
    _name = 'cost.pool'
    _description = 'Cost Pool'
    _rec_name = 'name'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: наследование для автогенерации кодов

    name = fields.Char(string='Pool Name', required=True)
    code = fields.Char(string='Pool Code', readonly=True, copy=False)  # ДОБАВЛЕНО: поле кода
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
    driver_id = fields.One2many('cost.driver', 'pool_id', string='Cost Drivers')
    available_driver_ids = fields.Many2many('cost.driver',
                                            compute='_compute_available_drivers',
                                            string='Available Drivers')

    # ДОБАВЛЕНО: поле company_id для multi-company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends()
    def _compute_available_drivers(self):
        for pool in self:
            # Показать драйверы без пула
            available = self.env['cost.driver'].search([('pool_id', '=', False)])
            pool.available_driver_ids = available

    @api.depends('allocation_ids.monthly_cost')
    def _compute_total_cost(self):
        for pool in self:
            employee_cost = sum(pool.allocation_ids.mapped('monthly_cost'))


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ДОБАВЛЕНО: автогенерация кода
            if not vals.get('code'):
                vals['code'] = self._generate_code('cost.pool.code')
        return super().create(vals_list)

    def action_reassign_drivers(self):
        """Открыть список всех драйверов для перепривязки"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reassign Cost Drivers',
            'res_model': 'cost.driver',
            'view_mode': 'tree,form',
            'target': 'new',
            'context': {
                'default_pool_id': self.id,
                'reassign_mode': True
            },
            'domain': []  # Показать все драйверы
        }

    def action_create_driver(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cost.driver',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_pool_id': self.id}
        }


class CostPoolAllocation(models.Model):
    _name = 'cost.pool.allocation'
    _description = 'Cost Pool Employee Allocation'

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True, ondelete='cascade')
    employee_cost_id = fields.Many2one('cost.employee', string='Employee', required=True)

    # Процент как обычное число от 0 до 100
    percentage = fields.Float(string='Allocation %', required=True, default=100.0,
                              help='Percentage of employee time allocated to this pool (0-100)')
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