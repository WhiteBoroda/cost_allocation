# models/service_costing.py

from odoo import models, fields, api
from datetime import datetime, timedelta


class ServiceCostCalculation(models.Model):
    _name = 'service.cost.calculation'
    _description = 'Service Cost Calculation'
    _rec_name = 'display_name'

    # Basic info
    service_catalog_id = fields.Many2one('service.catalog', string='Service', required=True)
    service_type_id = fields.Many2one('service.type', string='Service Type', readonly=False)
    client_id = fields.Many2one('res.partner', string='Client', domain=[('is_company', '=', True)],
                                help='Client for whom calculation is performed - affects support level')
    calculation_date = fields.Date(string='Calculation Date', default=fields.Date.today)

    # Cost breakdown
    direct_cost_per_unit = fields.Float(string='Direct Cost per Unit', compute='_compute_direct_cost_per_unit',
                                        store=True)
    indirect_cost_per_unit = fields.Float(string='Indirect Cost per Unit')
    admin_cost_per_unit = fields.Float(string='Admin Cost per Unit')
    overhead_cost_per_unit = fields.Float(string='Overhead Cost per Unit')

    total_cost_per_unit = fields.Float(string='Total Cost per Unit', compute='_compute_total_cost', store=True)

    # Calculation method
    calculation_method = fields.Selection([
        ('time_based', 'Time-based (hours)'),
        ('unit_based', 'Unit-based with Workload Factor'),
        ('complexity_based', 'Complexity-based')
    ], string='Calculation Method', default='time_based')

    # For time-based calculation
    estimated_hours_per_unit = fields.Float(string='Estimated Hours per Unit', default=1.0)
    blended_hourly_rate = fields.Float(string='Blended Hourly Rate', compute='_compute_blended_rate', store=True)

    # For unit-based with workload factor
    base_units_requested = fields.Float(string='Base Units Requested', default=1.0)
    actual_units_required = fields.Float(string='Actual Units Required', compute='_compute_actual_units', store=True)
    base_workload_factor = fields.Float(string='Base Workload Factor', compute='_compute_base_workload_factor',
                                        store=True, readonly=True)
    effective_workload_factor = fields.Float(string='Effective Workload Factor', compute='_compute_effective_workload',
                                             store=True,
                                             help='Workload factor adjusted by client support level')

    # For complexity-based
    complexity_multiplier = fields.Float(string='Complexity Multiplier', default=1.0)

    # Display
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('service_catalog_id')
    def _compute_service_type(self):
        """Get service type from related models if available"""
        for calc in self:
            # Пытаемся найти связанный ServiceType через категорию или другие связи
            service_type = False
            if calc.service_catalog_id and hasattr(calc.service_catalog_id, 'service_type_id'):
                service_type = calc.service_catalog_id.service_type_id
            elif calc.service_catalog_id and calc.service_catalog_id.category_id:
                # Ищем ServiceType по категории и названию
                service_type = self.env['service.type'].search([
                    ('category_id', '=', calc.service_catalog_id.category_id.id),
                    ('name', 'ilike', calc.service_catalog_id.name)
                ], limit=1)
            calc.service_type_id = service_type

    @api.depends('base_units_requested', 'effective_workload_factor', 'calculation_method')
    def _compute_actual_units(self):
        """Calculate actual units based on effective workload factor"""
        for calc in self:
            if calc.calculation_method == 'unit_based':
                calc.actual_units_required = calc.base_units_requested * (calc.effective_workload_factor or 1.0)
            else:
                calc.actual_units_required = calc.base_units_requested

    @api.depends('service_type_id', 'service_type_id.workload_factor')
    def _compute_base_workload_factor(self):
        """Get base workload factor from service type"""
        for calc in self:
            calc.base_workload_factor = calc.service_type_id.workload_factor if calc.service_type_id else 1.0

    @api.depends('base_workload_factor', 'client_id.support_level', 'client_id.workload_multiplier')
    def _compute_effective_workload(self):
        """Calculate effective workload factor including client support level"""
        for calc in self:
            if calc.client_id and calc.base_workload_factor:
                calc.effective_workload_factor = calc.client_id.get_effective_workload_factor(calc.base_workload_factor)
            else:
                calc.effective_workload_factor = calc.base_workload_factor or 1.0

    @api.depends('service_catalog_id', 'calculation_method', 'effective_workload_factor', 'actual_units_required',
                 'blended_hourly_rate', 'complexity_multiplier')
    def _compute_direct_cost_per_unit(self):
        """Calculate direct cost per unit based on method and effective workload factor"""
        for calc in self:
            if calc.calculation_method == 'time_based':
                # Время * ставка с учетом effective_workload_factor
                hours_with_workload = calc.estimated_hours_per_unit * (calc.effective_workload_factor or 1.0)
                calc.direct_cost_per_unit = hours_with_workload * calc.blended_hourly_rate

            elif calc.calculation_method == 'unit_based':
                # Базовая цена с учетом effective_workload_factor
                base_price = calc.service_catalog_id.base_cost if calc.service_catalog_id else 0
                calc.direct_cost_per_unit = base_price * (calc.effective_workload_factor or 1.0)

            elif calc.calculation_method == 'complexity_based':
                # Базовая цена * сложность * effective_workload_factor
                base_price = calc.service_catalog_id.base_cost if calc.service_catalog_id else 0
                calc.direct_cost_per_unit = base_price * calc.complexity_multiplier * (
                            calc.effective_workload_factor or 1.0)

            else:
                calc.direct_cost_per_unit = 0

    @api.depends('service_catalog_id', 'client_id.support_level', 'effective_workload_factor', 'calculation_date')
    def _compute_display_name(self):
        for calc in self:
            if calc.service_catalog_id:
                parts = [calc.service_catalog_id.name]
                if calc.client_id:
                    parts.append(
                        f"({calc.client_id.support_level.title() if calc.client_id.support_level else 'Standard'})")
                if calc.effective_workload_factor != 1.0:
                    parts.append(f"WF: {calc.effective_workload_factor}")
                parts.append(str(calc.calculation_date))
                calc.display_name = " - ".join(parts)
            else:
                calc.display_name = "New Calculation"

    @api.depends('direct_cost_per_unit', 'indirect_cost_per_unit', 'admin_cost_per_unit', 'overhead_cost_per_unit')
    def _compute_total_cost(self):
        for calc in self:
            calc.total_cost_per_unit = (calc.direct_cost_per_unit +
                                        calc.indirect_cost_per_unit +
                                        calc.admin_cost_per_unit +
                                        calc.overhead_cost_per_unit)

    @api.depends('service_type_id', 'service_type_id.default_responsible_ids')
    def _compute_blended_rate(self):
        """Calculate blended hourly rate based on service type and team"""
        for calc in self:
            if calc.service_type_id and calc.service_type_id.default_responsible_ids:
                # Берем среднюю ставку команды поддержки
                employees = calc.service_type_id.default_responsible_ids
                if employees:
                    # Здесь можно добавить логику расчета средней ставки
                    # Пока используем базовую ставку из настроек компании
                    calc.blended_hourly_rate = 50.0  # или из настроек
                else:
                    calc.blended_hourly_rate = 40.0  # дефолтная ставка
            else:
                calc.blended_hourly_rate = 40.0

    def get_effective_workload_units(self):
        """Get total effective workload units for reporting (includes client support level)"""
        self.ensure_one()
        if self.calculation_method == 'unit_based':
            return self.actual_units_required
        elif self.calculation_method == 'time_based':
            return self.estimated_hours_per_unit * (self.effective_workload_factor or 1.0)
        else:
            return self.effective_workload_factor or 1.0

    def action_calculate_costs(self):
        """Manual recalculation of costs"""
        for record in self:
            # Force recompute of all cost fields
            record._compute_base_workload_factor()
            record._compute_effective_workload()
            record._compute_actual_units()
            record._compute_direct_cost_per_unit()
            record._compute_blended_rate()
            record._compute_total_cost()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Costs recalculated successfully!',
                'type': 'success',
                'sticky': False,
            }
        }