# models/service_costing.py - новый файл для расчета стоимости сервисов

from odoo import models, fields, api
from datetime import datetime, timedelta


class ServiceCostCalculation(models.Model):
    _name = 'service.cost.calculation'
    _description = 'Service Cost Calculation'
    _rec_name = 'display_name'

    # Basic info
    service_catalog_id = fields.Many2one('service.catalog', string='Service', required=True)
    calculation_date = fields.Date(string='Calculation Date', default=fields.Date.today)

    # Cost breakdown
    direct_cost_per_unit = fields.Float(string='Direct Cost per Unit')
    indirect_cost_per_unit = fields.Float(string='Indirect Cost per Unit')
    admin_cost_per_unit = fields.Float(string='Admin Cost per Unit')
    overhead_cost_per_unit = fields.Float(string='Overhead Cost per Unit')

    total_cost_per_unit = fields.Float(string='Total Cost per Unit', compute='_compute_total_cost')

    # Calculation method
    calculation_method = fields.Selection([
        ('time_based', 'Time-based (hours)'),
        ('unit_based', 'Unit-based'),
        ('complexity_based', 'Complexity-based')
    ], string='Calculation Method', default='time_based')

    # For time-based calculation
    estimated_hours_per_unit = fields.Float(string='Estimated Hours per Unit', default=1.0)
    blended_hourly_rate = fields.Float(string='Blended Hourly Rate', compute='_compute_blended_rate')

    # For complexity-based
    complexity_multiplier = fields.Float(string='Complexity Multiplier', default=1.0)

    # Display
    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('service_catalog_id', 'calculation_date')
    def _compute_display_name(self):
        for calc in self:
            if calc.service_catalog_id:
                calc.display_name = f"{calc.service_catalog_id.name} - {calc.calculation_date}"
            else:
                calc.display_name = "New Calculation"

    @api.depends('direct_cost_per_unit', 'indirect_cost_per_unit', 'admin_cost_per_unit', 'overhead_cost_per_unit')
    def _compute_total_cost(self):
        for calc in self:
            calc.total_cost_per_unit = (calc.direct_cost_per_unit +
                                        calc.indirect_cost_per_unit +
                                        calc.admin_cost_per_unit +
                                        calc.overhead_cost_per_unit)

    @api.depends('service_catalog_id')
    def _compute_blended_rate(self):
        """Calculate blended hourly rate from responsible team"""
        for calc in self:
            if calc.service_catalog_id and calc.service_catalog_id.category_id:
                # Get service types for this category
                service_types = self.env['service.type'].search([
                    ('category_id', '=', calc.service_catalog_id.category_id.id)
                ])

                total_rate = 0
                team_count = 0

                for service_type in service_types:
                    if service_type.default_responsible_ids:
                        for employee in service_type.default_responsible_ids:
                            employee_cost = self.env['cost.employee'].search([
                                ('employee_id', '=', employee.id)
                            ], limit=1)
                            if employee_cost:
                                total_rate += employee_cost.hourly_cost
                                team_count += 1

                calc.blended_hourly_rate = total_rate / team_count if team_count > 0 else 0

    def action_calculate_costs(self):
        """Calculate all cost components"""
        self.ensure_one()

        # 1. Calculate direct costs
        self._calculate_direct_costs()

        # 2. Calculate indirect costs
        self._calculate_indirect_costs()

        # 3. Calculate admin costs
        self._calculate_admin_costs()

        # 4. Calculate overhead costs
        self._calculate_overhead_costs()

        # 5. Update service catalog with calculated cost
        self.service_catalog_id.base_cost = self.total_cost_per_unit

    def _calculate_direct_costs(self):
        """Calculate direct labor costs"""
        if self.calculation_method == 'time_based':
            self.direct_cost_per_unit = self.blended_hourly_rate * self.estimated_hours_per_unit
        elif self.calculation_method == 'complexity_based':
            base_rate = self.blended_hourly_rate * self.estimated_hours_per_unit
            self.direct_cost_per_unit = base_rate * self.complexity_multiplier
        else:  # unit_based
            # Use service type base price as starting point
            if self.service_catalog_id.category_id:
                service_types = self.env['service.type'].search([
                    ('category_id', '=', self.service_catalog_id.category_id.id)
                ], limit=1)
                if service_types:
                    self.direct_cost_per_unit = service_types[0].base_price * 0.6  # 60% for direct costs

    def _calculate_indirect_costs(self):
        """Calculate indirect costs based on cost drivers"""
        # Get all indirect cost pools
        indirect_pools = self.env['cost.pool'].search([
            ('pool_type', '=', 'indirect'),
            ('active', '=', True)
        ])

        total_indirect_cost = sum(indirect_pools.mapped('total_monthly_cost'))

        # Get total hours/units for allocation base
        total_allocation_base = self._get_total_allocation_base()

        if total_allocation_base > 0:
            cost_per_base_unit = total_indirect_cost / total_allocation_base

            if self.calculation_method == 'time_based':
                self.indirect_cost_per_unit = cost_per_base_unit * self.estimated_hours_per_unit
            else:
                self.indirect_cost_per_unit = cost_per_base_unit

    def _calculate_admin_costs(self):
        """Calculate administrative costs"""
        admin_pools = self.env['cost.pool'].search([
            ('pool_type', '=', 'admin'),
            ('active', '=', True)
        ])

        total_admin_cost = sum(admin_pools.mapped('total_monthly_cost'))

        # Allocate admin costs proportionally to direct + indirect
        base_cost = self.direct_cost_per_unit + self.indirect_cost_per_unit

        if base_cost > 0:
            # Get admin percentage from configuration (default 15%)
            admin_percentage = float(self.env['ir.config_parameter'].sudo().get_param(
                'cost_allocation.admin_cost_percentage', '15.0'
            )) / 100.0

            self.admin_cost_per_unit = base_cost * admin_percentage
        else:
            # If no base cost, distribute admin costs proportionally
            if total_admin_cost > 0:
                total_allocation_base = self._get_total_allocation_base()
                if total_allocation_base > 0:
                    admin_per_base_unit = total_admin_cost / total_allocation_base
                    if self.calculation_method == 'time_based':
                        self.admin_cost_per_unit = admin_per_base_unit * self.estimated_hours_per_unit
                    else:
                        self.admin_cost_per_unit = admin_per_base_unit

    def _calculate_overhead_costs(self):
        """Calculate overhead costs allocation"""
        # Get overhead costs from all pools
        overhead_allocations = self.env['cost.pool.overhead.allocation'].search([])
        total_overhead = sum(overhead_allocations.mapped('monthly_cost'))

        # Similar to indirect costs allocation
        total_allocation_base = self._get_total_allocation_base()

        if total_allocation_base > 0:
            overhead_per_base_unit = total_overhead / total_allocation_base

            if self.calculation_method == 'time_based':
                self.overhead_cost_per_unit = overhead_per_base_unit * self.estimated_hours_per_unit
            else:
                self.overhead_cost_per_unit = overhead_per_base_unit

    def _get_total_allocation_base(self):
        """Get total allocation base (hours, units, etc.) - УЛУЧШЕНО: динамический расчет"""
        # This should be calculated based on historical data or estimates


        # Get total estimated monthly capacity using dynamic working hours
        total_employees = self.env['cost.employee'].search_count([('active', '=', True)])

        if total_employees == 0:
            return 1.0  # Avoid division by zero

        # Calculate average working hours from employee cost configurations
        employee_costs = self.env['cost.employee'].search([('active', '=', True)])

        if employee_costs:
            # Use actual calculated working hours from employee configurations
            total_working_hours = sum(employee_costs.mapped('monthly_hours'))
            average_working_hours = total_working_hours / len(employee_costs)
        else:
            # Fallback to dynamic calculation for current month
            working_util = self.env['working.days.util']
            average_working_hours = working_util.get_current_month_working_hours()

        utilization_rate = 0.75  # 75% utilization - это можно сделать настраиваемым

        return total_employees * average_working_hours * utilization_rate

    def _calculate_allocation_base_for_period(self, period_date):
        """Calculate allocation base for specific period"""
        # Get total estimated capacity for specific month
        total_employees = self.env['cost.employee'].search_count([('active', '=', True)])

        if total_employees == 0:
            return 1.0

        # Get working hours for specific period
        working_util = self.env['working.days.util']
        working_hours_in_period = working_util.get_working_hours_in_month(
            period_date.year,
            period_date.month
        )

        # Get utilization rate from settings (default 75%)
        utilization_rate = float(self.env['ir.config_parameter'].sudo().get_param(
            'cost_allocation.utilization_rate', '0.75'
        ))

        return total_employees * working_hours_in_period * utilization_rate

    def _get_employee_capacity_for_month(self, employee_id, year, month):
        """Get specific employee capacity for given month"""
        employee_cost = self.env['cost.employee'].search([
            ('employee_id', '=', employee_id),
            ('active', '=', True)
        ], limit=1)

        if employee_cost and employee_cost.use_dynamic_hours:
            # Use employee's specific calendar if set
            working_util = self.env['working.days.util']
            calendar_id = employee_cost.resource_calendar_id.id if employee_cost.resource_calendar_id else None

            return working_util.get_working_hours_in_month(year, month, calendar_id)
        elif employee_cost:
            return employee_cost.monthly_hours
        else:
            # Fallback to company default
            working_util = self.env['working.days.util']
            return working_util.get_working_hours_in_month(year, month)


# Extend Service Catalog model
class ServiceCatalogExtended(models.Model):
    _inherit = 'service.catalog'

    # Cost calculation
    cost_calculation_ids = fields.One2many('service.cost.calculation', 'service_catalog_id',
                                           string='Cost Calculations')
    last_calculation_date = fields.Date(string='Last Calculation Date',
                                        compute='_compute_last_calculation')
    cost_calculation_method = fields.Selection([
        ('manual', 'Manual'),
        ('calculated', 'ABC Calculated'),
        ('hybrid', 'Hybrid (Manual + Calculated)')
    ], string='Costing Method', default='manual')

    # Override base_cost to show it can be calculated
    base_cost = fields.Float(string='Base Cost',
                             help="Base cost per unit - can be manually set or calculated using ABC costing")

    @api.depends('cost_calculation_ids.calculation_date')
    def _compute_last_calculation(self):
        for service in self:
            if service.cost_calculation_ids:
                service.last_calculation_date = max(service.cost_calculation_ids.mapped('calculation_date'))
            else:
                service.last_calculation_date = False

    def action_calculate_cost(self):
        """Create new cost calculation"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Calculate Service Cost',
            'res_model': 'service.cost.calculation',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_service_catalog_id': self.id,
                'default_calculation_method': 'time_based'
            }
        }

    def action_view_calculations(self):
        """View cost calculations history"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cost Calculations',
            'res_model': 'service.cost.calculation',
            'view_mode': 'tree,form',
            'domain': [('service_catalog_id', '=', self.id)],
            'context': {'default_service_catalog_id': self.id}
        }