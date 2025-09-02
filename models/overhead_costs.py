# models/overhead_costs.py - ПОЛНЫЙ КОД с поддержкой годовых затрат

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class CompanyOverheadCost(models.Model):
    _name = 'company.overhead.cost'
    _description = 'Company Overhead Costs'
    _order = 'sequence, name'
    _inherit = ['sequence.helper']

    # Basic info - СУЩЕСТВУЮЩИЕ ПОЛЯ
    code = fields.Char(string='Cost Code', readonly=True, copy=False)
    name = fields.Char(string='Cost Name', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    # Cost details - СУЩЕСТВУЮЩИЕ ПОЛЯ
    cost_type = fields.Selection([
        ('rent', 'Office Rent'),
        ('utilities', 'Utilities (Electricity, Water, Internet)'),
        ('transport', 'Transport & Vehicle Costs'),
        ('software', 'Software Subscriptions'),
        ('insurance', 'Insurance'),
        ('licenses', 'Licenses & Permits'),
        ('marketing', 'Marketing & Advertising'),
        ('legal', 'Legal & Professional Services'),
        ('office_supplies', 'Office Supplies'),
        ('equipment_lease', 'Equipment Lease'),
        ('bank_fees', 'Bank Fees'),
        ('taxes', 'Taxes & Government Fees'),
        ('other', 'Other Overhead')
    ], string='Cost Type', required=True)

    # ==================== НОВЫЕ ПОЛЯ ДЛЯ ПОДДЕРЖКИ ГОДОВЫХ ЗАТРАТ ====================

    # Исходная стоимость и период
    cost_amount = fields.Monetary(
        string='Cost Amount',
        currency_field='cost_currency_id',
        help='Original cost amount in purchase currency (e.g., annual license cost)'
    )

    cost_currency_id = fields.Many2one(
        'res.currency',
        string='Cost Currency',
        help='Currency in which the cost was incurred (EUR, USD, UAH, etc.)'
    )

    cost_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
        ('one_time', 'One Time')
    ], string='Cost Period', default='monthly',
        help='How often this cost is incurred')

    # ИЗМЕНЕННОЕ ПОЛЕ: monthly_amount теперь computed
    monthly_amount = fields.Float(
        string='Monthly Amount',
        compute='_compute_monthly_amount',
        store=True,
        help='Monthly amount in company currency (computed from cost_amount and period)'
    )

    # СУЩЕСТВУЮЩЕЕ ПОЛЕ
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Period - СУЩЕСТВУЮЩИЕ ПОЛЯ
    start_date = fields.Date(string='Start Date', default=fields.Date.today)
    end_date = fields.Date(string='End Date')

    # Allocation - СУЩЕСТВУЮЩИЕ ПОЛЯ
    pool_id = fields.Many2one('cost.pool', string='Allocate to Cost Pool',
                              domain=[('pool_type', 'in', ['indirect', 'admin'])],
                              required=True)
    allocation_method = fields.Selection([
        ('full', 'Full Amount'),
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Allocation Method', default='full', required=True)

    allocation_percentage = fields.Float(string='Allocation %', default=100.0)
    allocation_amount = fields.Float(string='Allocation Amount', compute='_compute_allocation_amount', store=True)

    # Company - СУЩЕСТВУЮЩЕЕ ПОЛЕ
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    # Supplier info - СУЩЕСТВУЮЩИЕ ПОЛЯ
    supplier_id = fields.Many2one('res.partner', string='Supplier/Vendor',
                                  domain=[('is_company', '=', True)])
    contract_reference = fields.Char(string='Contract Reference')

    # Status - СУЩЕСТВУЮЩЕЕ ПОЛЕ
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired')
    ], string='Status', default='draft', required=True)

    # ==================== COMPUTED METHODS ====================

    @api.depends('cost_amount', 'cost_currency_id', 'cost_period', 'currency_id')
    def _compute_monthly_amount(self):
        """НОВЫЙ МЕТОД: Compute monthly amount from original cost and period"""
        for cost in self:
            if cost.cost_amount and cost.cost_currency_id:
                # Конвертируем валюту в валюту компании
                if cost.cost_currency_id == cost.currency_id:
                    converted_amount = cost.cost_amount
                else:
                    converted_amount = cost.cost_currency_id._convert(
                        cost.cost_amount,
                        cost.currency_id,
                        cost.company_id,
                        fields.Date.today()
                    )

                # Пересчитываем в месячную сумму в зависимости от периода
                period_multipliers = {
                    'monthly': 1,
                    'quarterly': 1 / 3,
                    'annual': 1 / 12,
                    'one_time': 1 / 12,  # Амортизируем на год
                }
                multiplier = period_multipliers.get(cost.cost_period, 1)
                cost.monthly_amount = converted_amount * multiplier
            else:
                # Fallback - если новые поля не заполнены, сохраняем существующее поведение
                # Это обеспечивает совместимость со старыми записями
                if not cost.cost_amount:
                    cost.monthly_amount = cost.monthly_amount or 0.0

    @api.depends('monthly_amount', 'allocation_method', 'allocation_percentage')
    def _compute_allocation_amount(self):
        """СУЩЕСТВУЮЩИЙ МЕТОД: без изменений"""
        for cost in self:
            if cost.allocation_method == 'full':
                cost.allocation_amount = cost.monthly_amount
            elif cost.allocation_method == 'percentage':
                cost.allocation_amount = cost.monthly_amount * (cost.allocation_percentage / 100)
            else:  # fixed
                cost.allocation_amount = cost.allocation_amount

    # ==================== СУЩЕСТВУЮЩИЕ МЕТОДЫ ====================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('company.overhead.cost.code')

            # НОВОЕ: устанавливаем defaults для новых полей
            if not vals.get('cost_currency_id'):
                vals['cost_currency_id'] = self.env.company.currency_id.id
            if not vals.get('cost_period'):
                vals['cost_period'] = 'monthly'
            # Миграция старых записей: если есть monthly_amount но нет cost_amount
            if vals.get('monthly_amount') and not vals.get('cost_amount'):
                vals['cost_amount'] = vals['monthly_amount']

        return super().create(vals_list)

    def action_activate(self):
        """СУЩЕСТВУЮЩИЙ МЕТОД: Activate overhead cost"""
        self.state = 'active'
        # Update pool allocation
        self._update_pool_allocation()

    def action_expire(self):
        """СУЩЕСТВУЮЩИЙ МЕТОД: Mark as expired"""
        self.state = 'expired'
        # Remove from pool allocation
        self._remove_pool_allocation()

    def _update_pool_allocation(self):
        """СУЩЕСТВУЮЩИЙ МЕТОД: Update cost pool with this overhead cost"""
        if self.pool_id and self.state == 'active':
            # Find or create pool allocation for overhead
            allocation = self.env['cost.pool.overhead.allocation'].search([
                ('pool_id', '=', self.pool_id.id),
                ('overhead_cost_id', '=', self.id)
            ])

            if allocation:
                allocation.monthly_cost = self.allocation_amount
            else:
                self.env['cost.pool.overhead.allocation'].create({
                    'pool_id': self.pool_id.id,
                    'overhead_cost_id': self.id,
                    'monthly_cost': self.allocation_amount,
                    'allocation_date': fields.Date.today()
                })

    def _remove_pool_allocation(self):
        """СУЩЕСТВУЮЩИЙ МЕТОД: Remove pool allocation"""
        allocations = self.env['cost.pool.overhead.allocation'].search([
            ('overhead_cost_id', '=', self.id)
        ])
        allocations.unlink()

    def write(self, vals):
        """СУЩЕСТВУЮЩИЙ МЕТОД: Override write to update pool allocations"""
        result = super().write(vals)

        # Update allocations if amount or pool changed
        if any(field in vals for field in ['allocation_amount', 'pool_id', 'state']):
            for record in self:
                if record.state == 'active':
                    record._update_pool_allocation()
                else:
                    record._remove_pool_allocation()

        return result

    def toggle_active(self):
        """СУЩЕСТВУЮЩИЙ МЕТОД: Quick toggle for active state"""
        for record in self:
            if record.active and record.state == 'draft':
                record.action_activate()
            elif not record.active and record.state == 'active':
                record.state = 'draft'
                record._remove_pool_allocation()

    # ==================== НОВЫЕ UTILITY METHODS ====================

    def get_annual_total(self):
        """Get annual total cost"""
        self.ensure_one()
        return self.monthly_amount * 12

    def get_cost_in_currency(self, target_currency):
        """Get cost amount in specific currency"""
        self.ensure_one()
        if not target_currency:
            return self.cost_amount

        if self.cost_currency_id == target_currency:
            return self.cost_amount
        else:
            return self.cost_currency_id._convert(
                self.cost_amount,
                target_currency,
                self.company_id,
                fields.Date.today()
            )

    def get_period_description(self):
        """Get human-readable period description"""
        self.ensure_one()
        descriptions = {
            'monthly': 'Monthly recurring cost',
            'quarterly': 'Quarterly recurring cost (divided by 3 for monthly allocation)',
            'annual': 'Annual recurring cost (divided by 12 for monthly allocation)',
            'one_time': 'One-time cost (amortized over 12 months)',
        }
        return descriptions.get(self.cost_period, 'Unknown period')


class CostPoolOverheadAllocation(models.Model):
    """СУЩЕСТВУЮЩАЯ МОДЕЛЬ: без изменений"""
    _name = 'cost.pool.overhead.allocation'
    _description = 'Cost Pool Overhead Allocation'

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True, ondelete='cascade')
    overhead_cost_id = fields.Many2one('company.overhead.cost', string='Overhead Cost',
                                       required=True, ondelete='cascade')
    monthly_cost = fields.Float(string='Monthly Allocation', required=True)
    allocation_date = fields.Date(string='Allocation Date', default=fields.Date.today)


class CostPoolExtended(models.Model):
    """СУЩЕСТВУЮЩАЯ МОДЕЛЬ: без изменений"""
    _inherit = 'cost.pool'

    # Add overhead allocations
    overhead_allocation_ids = fields.One2many('cost.pool.overhead.allocation', 'pool_id',
                                              string='Overhead Allocations')
    total_overhead_cost = fields.Float(string='Total Overhead Cost',
                                       compute='_compute_overhead_cost', store=True)

    @api.depends('overhead_allocation_ids.monthly_cost')
    def _compute_overhead_cost(self):
        for pool in self:
            pool.total_overhead_cost = sum(pool.overhead_allocation_ids.mapped('monthly_cost'))

    # Override total cost calculation to include overhead
    @api.depends('allocation_ids.monthly_cost', 'overhead_allocation_ids.monthly_cost')
    def _compute_total_cost(self):
        for pool in self:
            employee_cost = sum(pool.allocation_ids.mapped('monthly_cost'))
            overhead_cost = sum(pool.overhead_allocation_ids.mapped('monthly_cost'))
            pool.total_monthly_cost = employee_cost + overhead_cost