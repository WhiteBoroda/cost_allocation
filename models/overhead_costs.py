from odoo import models, fields, api
from datetime import datetime


class CompanyOverheadCost(models.Model):
    _name = 'company.overhead.cost'
    _description = 'Company Overhead Costs'
    _order = 'sequence, name'
    _inherit = ['sequence.helper']

    # Basic info
    code = fields.Char(string='Cost Code', readonly=True, copy=False)
    name = fields.Char(string='Cost Name', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    # Cost details
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

    # Financial
    monthly_amount = fields.Float(string='Monthly Amount', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Period
    start_date = fields.Date(string='Start Date', default=fields.Date.today)
    end_date = fields.Date(string='End Date')

    # Allocation
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

    # Company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    # Supplier info (optional)
    supplier_id = fields.Many2one('res.partner', string='Supplier/Vendor',
                                  domain=[('is_company', '=', True)])
    contract_reference = fields.Char(string='Contract Reference')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired')
    ], string='Status', default='draft', required=True)

    @api.depends('monthly_amount', 'allocation_method', 'allocation_percentage')
    def _compute_allocation_amount(self):
        for cost in self:
            if cost.allocation_method == 'full':
                cost.allocation_amount = cost.monthly_amount
            elif cost.allocation_method == 'percentage':
                cost.allocation_amount = cost.monthly_amount * (cost.allocation_percentage / 100)
            else:  # fixed
                cost.allocation_amount = cost.allocation_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('company.overhead.cost.code')
        return super().create(vals_list)

    def action_activate(self):
        """Activate overhead cost"""
        self.state = 'active'
        # Update pool allocation
        self._update_pool_allocation()

    def action_expire(self):
        """Mark as expired"""
        self.state = 'expired'
        # Remove from pool allocation
        self._remove_pool_allocation()

    def _update_pool_allocation(self):
        """Update cost pool with this overhead cost"""
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
                    'monthly_cost': self.allocation_amount
                })

    def _remove_pool_allocation(self):
        """Remove from cost pool allocation"""
        allocations = self.env['cost.pool.overhead.allocation'].search([
            ('overhead_cost_id', '=', self.id)
        ])
        allocations.unlink()

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.end_date and self.end_date < fields.Date.today():
            self.state = 'expired'


class CostPoolOverheadAllocation(models.Model):
    _name = 'cost.pool.overhead.allocation'
    _description = 'Cost Pool Overhead Allocation'

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True, ondelete='cascade')
    overhead_cost_id = fields.Many2one('company.overhead.cost', string='Overhead Cost',
                                       required=True, ondelete='cascade')
    monthly_cost = fields.Float(string='Monthly Allocation', required=True)
    allocation_date = fields.Date(string='Allocation Date', default=fields.Date.today)


class CostPoolExtended(models.Model):
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