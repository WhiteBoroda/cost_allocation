from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta


class ClientCostAllocation(models.Model):
    _name = 'client.cost.allocation'
    _description = 'Client Cost Allocation'
    _order = 'period_date desc, client_id'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'sequence.helper']

    # ДОБАВЛЕНО: поле кода
    code = fields.Char(string='Allocation Code', readonly=True, copy=False)
    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)], tracking=True)
    period_date = fields.Date(string='Period', required=True, default=fields.Date.today, tracking=True)

    # Cost breakdown
    direct_cost = fields.Monetary(string='Direct Costs', tracking=True, currency_field='currency_id')
    indirect_cost = fields.Monetary(string='Indirect Costs', compute='_compute_indirect_costs', store=True,
                                    currency_field='currency_id')
    admin_cost = fields.Monetary(string='Administrative Costs', compute='_compute_admin_costs', store=True,
                                 currency_field='currency_id')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost', store=True,
                                 currency_field='currency_id')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('confirmed', 'Confirmed')
    ], string='Status', default='draft', required=True, tracking=True)

    # Relations
    indirect_cost_ids = fields.One2many('client.indirect.cost', 'allocation_id', string='Indirect Costs Detail')

    # Display name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    # Currency
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('client_id', 'period_date')
    def _compute_display_name(self):
        for record in self:
            if record.client_id and record.period_date:
                record.display_name = f"{record.client_id.name} - {record.period_date.strftime('%Y-%m')}"
            else:
                record.display_name = "New Allocation"

    @api.depends('indirect_cost_ids.allocated_cost')
    def _compute_indirect_costs(self):
        for record in self:
            record.indirect_cost = sum(record.indirect_cost_ids.mapped('allocated_cost'))

    @api.depends('indirect_cost', 'total_cost')
    def _compute_admin_costs(self):
        """Administrative costs are allocated proportionally to other costs"""
        # Get total admin pool cost
        admin_pools = self.env['cost.pool'].search([('pool_type', '=', 'admin')])
        total_admin_cost = sum(admin_pools.mapped('total_monthly_cost'))

        if total_admin_cost > 0:
            # Group records by period to calculate proportional allocation
            periods = self.mapped('period_date')

            for period in periods:
                # Get all allocations for this period
                period_records = self.filtered(lambda r: r.period_date == period)
                all_allocations = self.search([('period_date', '=', period)])

                # Calculate total non-admin costs for this period
                total_non_admin = sum(all_allocations.mapped('direct_cost')) + sum(
                    all_allocations.mapped('indirect_cost'))

                # Allocate admin costs proportionally
                for record in period_records:
                    if total_non_admin > 0:
                        client_non_admin = record.direct_cost + record.indirect_cost
                        record.admin_cost = total_admin_cost * (client_non_admin / total_non_admin)
                    else:
                        record.admin_cost = 0
        else:
            for record in self:
                record.admin_cost = 0

    @api.depends('direct_cost', 'indirect_cost', 'admin_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.direct_cost + record.indirect_cost + record.admin_cost

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ДОБАВЛЕНО: автогенерация кода
            if not vals.get('code'):
                vals['code'] = self._generate_code('client.cost.allocation.code')
        return super().create(vals_list)

    def action_calculate_costs(self):
        """Calculate all costs for this allocation"""
        for record in self:
            # 1. Calculate direct costs from timesheets
            record._calculate_direct_costs()

            # 2. Calculate indirect costs from drivers
            record._calculate_indirect_costs()

            # 3. Admin costs will be calculated automatically via depends

            record.state = 'calculated'
            record.message_post(body="Cost calculation completed")

    def _calculate_direct_costs(self):
        """Calculate direct costs from timesheet entries"""
        self.ensure_one()

        # Get timesheet entries for this client and period
        domain = [
            ('project_id.partner_id', '=', self.client_id.id),
            ('date', '>=', self.period_date.replace(day=1)),
            ('date', '<=', self._get_month_end())
        ]

        timesheet_lines = self.env['account.analytic.line'].search(domain)

        total_direct_cost = 0
        for line in timesheet_lines:
            if line.employee_id:
                # Get employee hourly cost
                employee_cost = self.env['cost.employee'].search([
                    ('employee_id', '=', line.employee_id.id)
                ], limit=1)

                if employee_cost:
                    total_direct_cost += line.unit_amount * employee_cost.hourly_cost

        self.direct_cost = total_direct_cost

    def _calculate_indirect_costs(self):
        """Calculate indirect costs from cost drivers"""
        self.ensure_one()

        # Clear existing indirect costs
        self.indirect_cost_ids.unlink()

        # Get all cost drivers
        drivers = self.env['cost.driver'].search([])

        for driver in drivers:
            # Find client driver value
            client_driver = driver.client_driver_ids.filtered(
                lambda cd: cd.client_id == self.client_id
            )

            if client_driver:
                # Create indirect cost record
                self.env['client.indirect.cost'].create({
                    'allocation_id': self.id,
                    'driver_id': driver.id,
                    'quantity': client_driver.quantity,
                    'cost_per_unit': driver.cost_per_unit,
                    'allocated_cost': client_driver.allocated_cost
                })

    def _get_month_end(self):
        """Get last day of the period month"""
        if self.period_date.month == 12:
            return self.period_date.replace(year=self.period_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            return self.period_date.replace(month=self.period_date.month + 1, day=1) - timedelta(days=1)

    def action_confirm(self):
        """Confirm the allocation"""
        self.state = 'confirmed'
        self.message_post(body="Cost allocation confirmed")

    _sql_constraints = [
        ('unique_client_period', 'unique(client_id, period_date)',
         'Only one allocation per client per period is allowed!')]


class ClientIndirectCost(models.Model):
    _name = 'client.indirect.cost'
    _description = 'Client Indirect Cost Detail'

    allocation_id = fields.Many2one('client.cost.allocation', string='Allocation',
                                    required=True, ondelete='cascade')
    client_id = fields.Many2one(related='allocation_id.client_id', store=True)
    currency_id = fields.Many2one('res.currency', related='allocation_id.currency_id', store=True)

    driver_id = fields.Many2one('cost.driver', string='Cost Driver', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    cost_per_unit = fields.Monetary(string='Cost per Unit', currency_field='currency_id')
    allocated_cost = fields.Monetary(string='Allocated Cost', compute='_compute_allocated_cost', store=True,
                                     currency_field='currency_id')
    @api.depends('quantity', 'cost_per_unit')
    def _compute_allocated_cost(self):
        for record in self:
            record.allocated_cost = record.quantity * record.cost_per_unit