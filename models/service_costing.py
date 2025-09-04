# models/service_costing.py - ИНТЕГРАЦИЯ С ABC COSTING

from odoo import models, fields, api
from datetime import datetime, timedelta


class ServiceCostCalculation(models.Model):
    _name = 'service.cost.calculation'
    _description = 'Service Cost Calculation with ABC Costing Integration'
    _rec_name = 'display_name'

    # Basic info
    service_catalog_id = fields.Many2one('service.catalog', string='Service', required=True)
    service_type_id = fields.Many2one('service.type', string='Service Type')
    client_id = fields.Many2one('res.partner', string='Client', domain=[('is_company', '=', True)],
                                help='Client for whom calculation is performed - affects support level')
    calculation_date = fields.Date(string='Calculation Date', default=fields.Date.today)

    # Cost breakdown - ИНТЕГРИРОВАНО С ABC COSTING
    direct_cost_per_unit = fields.Float(string='Direct Cost per Unit', compute='_compute_direct_cost_per_unit',
                                        store=True)
    indirect_cost_per_unit = fields.Float(string='Indirect Cost per Unit', compute='_compute_indirect_cost_per_unit',
                                          store=True, help='Costs from indirect cost pools')
    admin_cost_per_unit = fields.Float(string='Admin Cost per Unit', compute='_compute_admin_cost_per_unit',
                                       store=True, help='Costs from administrative cost pools')
    overhead_cost_per_unit = fields.Float(string='Overhead Cost per Unit', compute='_compute_overhead_cost_per_unit',
                                          store=True, help='Company overhead costs (rent, utilities, etc.)')

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

    # ==================== ONCHANGE METHODS ====================

    @api.onchange('service_catalog_id')
    def _onchange_service_catalog(self):
        """Auto-fill service type when service catalog is selected"""
        if self.service_catalog_id:
            if self.service_catalog_id.service_type_id:
                self.service_type_id = self.service_catalog_id.service_type_id

    @api.onchange('service_type_id')
    def _onchange_service_type(self):
        """Auto-suggest service catalog when service type is selected"""
        if self.service_type_id and not self.service_catalog_id:
            service_catalog = self.env['service.catalog'].search([
                ('service_type_id', '=', self.service_type_id.id),
                ('active', '=', True)
            ], limit=1)
            if service_catalog:
                self.service_catalog_id = service_catalog

    # ==================== COMPUTED METHODS - DIRECT COSTS ====================

    @api.depends('service_type_id')
    def _compute_base_workload_factor(self):
        """Get base workload factor from service type"""
        for calc in self:
            if calc.service_type_id:
                calc.base_workload_factor = calc.service_type_id.base_workload_factor or 1.0
            else:
                calc.base_workload_factor = 1.0

    @api.depends('base_workload_factor', 'client_id.support_level')
    def _compute_effective_workload(self):
        """Calculate effective workload factor including client support level"""
        for calc in self:
            if calc.client_id and calc.base_workload_factor:
                if not calc.client_id.support_level:
                    calc.client_id.support_level = 'standard'

                multiplier_mapping = {
                    'basic': 0.8,
                    'standard': 1.0,
                    'premium': 1.3,
                    'enterprise': 1.6,
                }
                multiplier = multiplier_mapping.get(calc.client_id.support_level, 1.0)
                calc.effective_workload_factor = calc.base_workload_factor * multiplier
            else:
                calc.effective_workload_factor = calc.base_workload_factor or 1.0

    @api.depends('base_units_requested', 'effective_workload_factor', 'calculation_method')
    def _compute_actual_units(self):
        """Calculate actual units based on effective workload factor"""
        for calc in self:
            if calc.calculation_method == 'unit_based':
                calc.actual_units_required = calc.base_units_requested * (calc.effective_workload_factor or 1.0)
            else:
                calc.actual_units_required = calc.base_units_requested or 1.0

    @api.depends('service_type_id')
    def _compute_blended_rate(self):
        """Calculate blended hourly rate based on service type and team"""
        for calc in self:
            if calc.service_type_id and calc.service_type_id.default_responsible_ids:
                employees = calc.service_type_id.default_responsible_ids
                if employees:
                    # TODO: Расчет средней ставки из employee_cost записей
                    calc.blended_hourly_rate = 50.0
                else:
                    calc.blended_hourly_rate = 40.0
            else:
                calc.blended_hourly_rate = 40.0

    @api.depends('service_catalog_id', 'calculation_method', 'effective_workload_factor', 'actual_units_required',
                 'blended_hourly_rate', 'complexity_multiplier', 'estimated_hours_per_unit')
    def _compute_direct_cost_per_unit(self):
        """Calculate direct cost per unit based on method and effective workload factor"""
        for calc in self:
            if calc.calculation_method == 'time_based':
                hours_with_workload = calc.estimated_hours_per_unit * (calc.effective_workload_factor or 1.0)
                calc.direct_cost_per_unit = hours_with_workload * calc.blended_hourly_rate

            elif calc.calculation_method == 'unit_based':
                base_price = calc.service_catalog_id.base_cost or 0.0
                calc.direct_cost_per_unit = base_price * (calc.effective_workload_factor or 1.0)

            elif calc.calculation_method == 'complexity_based':
                base_price = calc.service_catalog_id.base_cost or 0.0
                calc.direct_cost_per_unit = (base_price * calc.complexity_multiplier *
                                             (calc.effective_workload_factor or 1.0))
            else:
                calc.direct_cost_per_unit = 0.0

    # ==================== COMPUTED METHODS - ABC COSTING INTEGRATION ====================

    @api.depends('service_type_id', 'actual_units_required', 'calculation_date')
    def _compute_indirect_cost_per_unit(self):
        """Calculate indirect costs from cost pools"""
        for calc in self:
            if not calc.service_type_id:
                calc.indirect_cost_per_unit = 0.0
                continue

            # Найти indirect cost pools связанные с типом сервиса
            indirect_pools = self.env['cost.pool'].search([
                ('pool_type', '=', 'indirect'),
                ('active', '=', True)
            ])

            total_indirect_cost = 0.0
            for pool in indirect_pools:
                # Найти cost driver для этого пула
                drivers = pool.driver_id
                for driver in drivers:
                    # Проверить есть ли allocation для нашего клиента
                    if calc.client_id:
                        client_allocation = self.env['client.cost.driver'].search([
                            ('driver_id', '=', driver.id),
                            ('client_id', '=', calc.client_id.id)
                        ])
                        if client_allocation:
                            # Рассчитать долю затрат для этого сервиса
                            service_cost = driver.cost_per_unit * calc.actual_units_required
                            total_indirect_cost += service_cost

            calc.indirect_cost_per_unit = total_indirect_cost

    @api.depends('service_type_id', 'actual_units_required', 'calculation_date', 'client_id')
    def _compute_admin_cost_per_unit(self):
        """Calculate admin costs from administrative cost pools"""
        for calc in self:
            if not calc.service_type_id:
                calc.admin_cost_per_unit = 0.0
                continue

            # НАЙТИ admin cost pools
            admin_pools = self.env['cost.pool'].search([
                ('pool_type', '=', 'admin'),
                ('active', '=', True)
            ])

            # DEBUG: логирование
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"=== ADMIN COST DEBUG for {calc.service_catalog_id.name} ===")
            _logger.info(f"Found {len(admin_pools)} admin pools: {admin_pools.mapped('name')}")

            if not admin_pools:
                _logger.warning("No admin cost pools found! Create pools with pool_type='admin'")
                calc.admin_cost_per_unit = 0.0
                continue

            total_admin_cost = 0.0
            for pool in admin_pools:
                pool_cost = 0.0
                drivers = pool.driver_id

                _logger.info(f"Pool '{pool.name}' has {len(drivers)} drivers: {drivers.mapped('name')}")

                if not drivers:
                    _logger.warning(f"Admin pool '{pool.name}' has NO DRIVERS attached!")
                    continue

                for driver in drivers:
                    driver_cost = 0.0
                    _logger.info(f"  Driver '{driver.name}': cost_per_unit = {driver.cost_per_unit}")

                    if driver.cost_per_unit == 0:
                        _logger.warning(f"    Driver '{driver.name}' has ZERO cost_per_unit!")
                        continue

                    if calc.client_id:
                        client_allocation = self.env['client.cost.driver'].search([
                            ('driver_id', '=', driver.id),
                            ('client_id', '=', calc.client_id.id)
                        ])

                        if client_allocation:
                            # ИСПРАВЛЕНО: используем количество из client_allocation, а не actual_units_required
                            driver_quantity = client_allocation.quantity or 0.0
                            driver_cost = driver.cost_per_unit * driver_quantity
                            _logger.info(f"    Client allocation found: quantity={driver_quantity}, cost={driver_cost}")
                        else:
                            _logger.warning(
                                f"    NO client allocation for driver '{driver.name}' and client '{calc.client_id.name}'")
                            # Можно добавить fallback логику
                            if calc.actual_units_required > 0:
                                driver_cost = driver.cost_per_unit * calc.actual_units_required
                                _logger.info(
                                    f"    Using fallback: actual_units={calc.actual_units_required}, cost={driver_cost}")

                    pool_cost += driver_cost

                _logger.info(f"  Pool '{pool.name}' total cost: {pool_cost}")
                total_admin_cost += pool_cost

            _logger.info(f"Total admin cost for service: {total_admin_cost}")
            calc.admin_cost_per_unit = total_admin_cost

    @api.depends('service_type_id', 'actual_units_required', 'calculation_date')
    def _compute_overhead_cost_per_unit(self):
        """Calculate overhead costs from company overhead costs"""
        for calc in self:
            if not calc.service_type_id:
                calc.overhead_cost_per_unit = 0.0
                continue

            # Найти активные overhead costs
            overhead_costs = self.env['company.overhead.cost'].search([
                ('state', '=', 'active'),
                ('company_id', '=', calc.env.company.id)
            ])

            total_overhead = sum(overhead_costs.mapped('allocation_amount'))

            if total_overhead > 0:
                # Распределить overhead пропорционально прямым затратам
                # TODO: Можно сделать более сложную логику распределения
                if calc.direct_cost_per_unit > 0:
                    # Пример: 20% от прямых затрат как overhead
                    calc.overhead_cost_per_unit = calc.direct_cost_per_unit * 0.20
                else:
                    calc.overhead_cost_per_unit = 10.0  # минимальный overhead
            else:
                calc.overhead_cost_per_unit = 0.0

    # ==================== DISPLAY AND TOTAL ====================

    @api.depends('service_catalog_id', 'client_id.support_level', 'effective_workload_factor', 'calculation_date')
    def _compute_display_name(self):
        for calc in self:
            if calc.service_catalog_id:
                parts = [calc.service_catalog_id.name]
                if calc.client_id:
                    support_level = calc.client_id.support_level or 'Standard'
                    parts.append(f"({support_level.title()})")
                if calc.effective_workload_factor and calc.effective_workload_factor != 1.0:
                    parts.append(f"WF: {calc.effective_workload_factor:.2f}")
                if calc.calculation_date:
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

    # ==================== UTILITY METHODS ====================

    def get_effective_workload_units(self):
        """Get total effective workload units for reporting"""
        self.ensure_one()
        if self.calculation_method == 'unit_based':
            return self.actual_units_required
        elif self.calculation_method == 'time_based':
            return self.estimated_hours_per_unit * (self.effective_workload_factor or 1.0)
        else:
            return self.effective_workload_factor or 1.0

    def action_calculate_costs(self):
        """Manual recalculation of all costs including ABC components"""
        for record in self:
            if record.client_id and not record.client_id.support_level:
                record.client_id.support_level = 'standard'

            # Принудительный пересчет всех computed полей
            record._compute_base_workload_factor()
            record._compute_effective_workload()
            record._compute_actual_units()
            record._compute_blended_rate()
            record._compute_direct_cost_per_unit()

            # ABC Costing components
            record._compute_indirect_cost_per_unit()
            record._compute_admin_cost_per_unit()
            record._compute_overhead_cost_per_unit()

            record._compute_total_cost()
            record._compute_display_name()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'All costs recalculated with ABC methodology!',
                'type': 'success',
                'sticky': False,
            }
        }

    def get_cost_breakdown(self):
        """Получить детализацию затрат для отчетов"""
        self.ensure_one()
        return {
            'direct_cost': self.direct_cost_per_unit,
            'indirect_cost': self.indirect_cost_per_unit,
            'admin_cost': self.admin_cost_per_unit,
            'overhead_cost': self.overhead_cost_per_unit,
            'total_cost': self.total_cost_per_unit,
            'workload_factor': self.effective_workload_factor,
            'service_name': self.service_catalog_id.name,
            'client_name': self.client_id.name if self.client_id else '',
            'calculation_method': self.calculation_method
        }

    def diagnose_admin_costs(self):
        """Диагностика проблем с расчетом административных затрат"""
        self.ensure_one()

        diagnosis = {
            'status': 'OK',
            'issues': [],
            'recommendations': [],
            'data': {}
        }

        # 1. Проверить наличие admin pools
        admin_pools = self.env['cost.pool'].search([
            ('pool_type', '=', 'admin'),
            ('active', '=', True)
        ])

        diagnosis['data']['admin_pools_count'] = len(admin_pools)
        diagnosis['data']['admin_pools'] = admin_pools.mapped('name')

        if not admin_pools:
            diagnosis['status'] = 'ERROR'
            diagnosis['issues'].append('No admin cost pools found')
            diagnosis['recommendations'].append('Create cost pools with type "Administrative Costs"')
            return diagnosis

        # 2. Проверить драйверы у admin pools
        total_drivers = 0
        pools_without_drivers = []

        for pool in admin_pools:
            drivers = pool.driver_id
            diagnosis['data'][f'pool_{pool.name}_drivers'] = drivers.mapped('name')

            if not drivers:
                pools_without_drivers.append(pool.name)
            else:
                total_drivers += len(drivers)

        if pools_without_drivers:
            diagnosis['status'] = 'WARNING'
            diagnosis['issues'].append(f'Pools without drivers: {", ".join(pools_without_drivers)}')
            diagnosis['recommendations'].append('Assign cost drivers to admin pools')

        # 3. Проверить client allocations
        if self.client_id and total_drivers > 0:
            missing_allocations = []
            zero_cost_drivers = []

            for pool in admin_pools:
                for driver in pool.driver_id:
                    # Проверить cost_per_unit
                    if driver.cost_per_unit == 0:
                        zero_cost_drivers.append(driver.name)

                    # Проверить client allocation
                    client_allocation = self.env['client.cost.driver'].search([
                        ('driver_id', '=', driver.id),
                        ('client_id', '=', self.client_id.id)
                    ])

                    if not client_allocation:
                        missing_allocations.append(f'{driver.name} for {self.client_id.name}')
                    else:
                        diagnosis['data'][f'allocation_{driver.name}'] = client_allocation.quantity

            if zero_cost_drivers:
                diagnosis['status'] = 'WARNING'
                diagnosis['issues'].append(f'Drivers with zero cost: {", ".join(zero_cost_drivers)}')
                diagnosis['recommendations'].append('Configure cost_per_unit for admin drivers')

            if missing_allocations:
                diagnosis['status'] = 'WARNING'
                diagnosis['issues'].append(
                    f'Missing client allocations: {", ".join(missing_allocations[:3])}{"..." if len(missing_allocations) > 3 else ""}')
                diagnosis['recommendations'].append(f'Create client cost driver records for {self.client_id.name}')

        # 4. Итоговый расчет
        diagnosis['data']['current_admin_cost'] = self.admin_cost_per_unit
        diagnosis['data']['actual_units_required'] = self.actual_units_required

        return diagnosis

    def action_diagnose_admin_costs(self):
        """Action для диагностики админских затрат"""
        diagnosis = self.diagnose_admin_costs()

        message = f"<h4>Admin Cost Diagnosis: {diagnosis['status']}</h4>"

        if diagnosis['issues']:
            message += "<h5>Issues Found:</h5><ul>"
            for issue in diagnosis['issues']:
                message += f"<li>{issue}</li>"
            message += "</ul>"

        if diagnosis['recommendations']:
            message += "<h5>Recommendations:</h5><ul>"
            for rec in diagnosis['recommendations']:
                message += f"<li>{rec}</li>"
            message += "</ul>"

        message += f"<h5>Current Data:</h5>"
        message += f"<p><strong>Admin Pools:</strong> {diagnosis['data'].get('admin_pools_count', 0)}</p>"
        message += f"<p><strong>Current Admin Cost:</strong> {diagnosis['data'].get('current_admin_cost', 0)}</p>"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Admin Cost Diagnosis',
                'message': message,
                'sticky': True,
                'type': 'warning' if diagnosis['status'] != 'OK' else 'success',
            }
        }