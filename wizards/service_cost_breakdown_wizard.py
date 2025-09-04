# wizards/service_cost_breakdown_wizard.py

from odoo import models, fields, api


class ServiceCostBreakdownWizard(models.TransientModel):
    _name = 'service.cost.breakdown.wizard'
    _description = 'Service Cost Breakdown Analysis'

    service_catalog_id = fields.Many2one('service.catalog', string='Service', required=True)

    # Service info
    service_name = fields.Char(related='service_catalog_id.name', readonly=True)
    service_code = fields.Char(related='service_catalog_id.code', readonly=True)
    support_hours_per_unit = fields.Float(related='service_catalog_id.support_hours_per_unit', readonly=True)

    # Cost breakdown - вычисляется в wizard'е
    base_cost = fields.Monetary(string='Base Cost', currency_field='currency_id',
                                compute='_compute_wizard_base_cost', readonly=True,
                                help='Computed: Average Hourly Cost × Support Hours')
    markup_percentage = fields.Float(related='service_catalog_id.markup_percentage', readonly=True)
    sales_price = fields.Monetary(related='service_catalog_id.sales_price', readonly=True)
    currency_id = fields.Many2one(related='service_catalog_id.currency_id', readonly=True)

    # Team info
    responsible_team_ids = fields.Many2many(related='service_catalog_id.service_type_id.default_responsible_ids',
                                            readonly=True)
    team_count = fields.Integer(string='Team Size', compute='_compute_team_stats', readonly=True)
    average_hourly_cost = fields.Float(string='Average Hourly Cost', compute='_compute_team_stats', readonly=True)

    # Employee cost lines
    employee_cost_line_ids = fields.One2many('service.cost.breakdown.line', 'wizard_id',
                                             string='Employee Cost Details')

    # Warning flag
    has_missing_records = fields.Boolean(string='Has Missing Cost Records',
                                         compute='_compute_missing_records', readonly=True)

    @api.depends('employee_cost_line_ids.has_cost_record')
    def _compute_missing_records(self):
        """Check if any employee is missing cost records"""
        for wizard in self:
            wizard.has_missing_records = any(not line.has_cost_record for line in wizard.employee_cost_line_ids)

    @api.depends('average_hourly_cost', 'support_hours_per_unit')
    def _compute_wizard_base_cost(self):
        """Compute base cost directly in wizard"""
        for wizard in self:
            wizard.base_cost = wizard.average_hourly_cost * wizard.support_hours_per_unit

    @api.depends('responsible_team_ids')
    def _compute_team_stats(self):
        """Calculate team stats from actual employee cost records"""
        for wizard in self:
            wizard.team_count = len(wizard.responsible_team_ids)

            # Ищем cost.employee записи напрямую
            if wizard.responsible_team_ids:
                employee_costs = self.env['cost.employee'].search([
                    ('employee_id', 'in', wizard.responsible_team_ids.ids),
                    ('active', '=', True)
                ])

                if employee_costs:
                    costs_with_rates = employee_costs.filtered(lambda c: c.hourly_cost > 0)
                    if costs_with_rates:
                        total_hourly = sum(costs_with_rates.mapped('hourly_cost'))
                        wizard.average_hourly_cost = total_hourly / len(costs_with_rates)
                    else:
                        wizard.average_hourly_cost = 0.0
                else:
                    wizard.average_hourly_cost = 0.0
            else:
                wizard.average_hourly_cost = 0.0

    @api.model
    def default_get(self, fields_list):
        """Pre-populate employee cost lines"""
        values = super().default_get(fields_list)

        service_catalog_id = self._context.get('default_service_catalog_id') or self._context.get('service_catalog_id')
        if service_catalog_id:
            service_catalog = self.env['service.catalog'].browse(service_catalog_id)
            values['service_catalog_id'] = service_catalog.id

            # DEBUG: логирование
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"=== WIZARD DEFAULT_GET DEBUG ===")
            _logger.info(f"Service: {service_catalog.name}")
            _logger.info(
                f"Service Type: {service_catalog.service_type_id.name if service_catalog.service_type_id else 'None'}")

            # Создать линии для сотрудников команды
            if service_catalog.service_type_id and service_catalog.service_type_id.default_responsible_ids:
                employees = service_catalog.service_type_id.default_responsible_ids
                _logger.info(f"Team members: {employees.mapped('name')}")

                employee_lines = []

                # Получить все cost.employee записи за один раз
                employee_costs = self.env['cost.employee'].search([
                    ('employee_id', 'in', employees.ids),
                    ('active', '=', True)
                ])
                employee_costs_data = {ec.employee_id.id: ec for ec in employee_costs}
                _logger.info(f"Found cost records for: {list(employee_costs_data.keys())}")

                # Создать линию для каждого сотрудника
                for employee in employees:
                    emp_cost = employee_costs_data.get(employee.id)

                    if emp_cost:
                        cost_per_unit = emp_cost.hourly_cost * (service_catalog.support_hours_per_unit or 1.0)
                        line_vals = {
                            'employee_id': employee.id,
                            'monthly_cost': emp_cost.monthly_total_cost,
                            'hourly_cost': emp_cost.hourly_cost,
                            'cost_per_service_unit': cost_per_unit,
                            'has_cost_record': True
                        }
                        _logger.info(f"Employee {employee.name}: {line_vals}")
                    else:
                        line_vals = {
                            'employee_id': employee.id,
                            'monthly_cost': 0.0,
                            'hourly_cost': 0.0,
                            'cost_per_service_unit': 0.0,
                            'has_cost_record': False
                        }
                        _logger.info(f"Employee {employee.name}: NO COST RECORD")

                    employee_lines.append((0, 0, line_vals))

                values['employee_cost_line_ids'] = employee_lines
                _logger.info(f"Created {len(employee_lines)} employee lines")
            else:
                _logger.warning("No service type or no responsible team!")

        return values

    def action_create_missing_cost_records(self):
        """Create missing employee cost records"""
        missing_employees = self.employee_cost_line_ids.filtered(lambda l: not l.has_cost_record)

        if not missing_employees:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'All employees already have cost records.',
                    'type': 'info',
                }
            }

        created_count = 0
        for line in missing_employees:
            # Create basic cost record with default values
            self.env['cost.employee'].create({
                'employee_id': line.employee_id.id,
                'monthly_salary': 50000.0,  # Default - user should update
                'use_manual': True,
                'manual_monthly_hours': 160.0,  # Default working hours
            })
            created_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Created {created_count} employee cost records. Please update with actual salary data.',
                'type': 'success',
            }
        }

    def action_debug_employee_costs(self):
        """Debug employee cost data"""
        debug_info = []

        # Check team
        debug_info.append(f"<h4>Team Analysis:</h4>")
        debug_info.append(f"<p>Team Size: {len(self.responsible_team_ids)}</p>")
        debug_info.append(f"<p>Team Members: {', '.join(self.responsible_team_ids.mapped('name'))}</p>")

        # Check cost.employee records
        if self.responsible_team_ids:
            debug_info.append(f"<h4>Cost Employee Records:</h4>")

            for employee in self.responsible_team_ids:
                cost_records = self.env['cost.employee'].search([
                    ('employee_id', '=', employee.id)
                ])

                if cost_records:
                    for cost_record in cost_records:
                        debug_info.append(f"<p><strong>{employee.name}:</strong></p>")
                        debug_info.append(f"<ul>")
                        debug_info.append(f"<li>Active: {cost_record.active}</li>")
                        debug_info.append(f"<li>Monthly Salary: {cost_record.monthly_salary}</li>")
                        debug_info.append(f"<li>Monthly Total Cost: {cost_record.monthly_total_cost}</li>")
                        debug_info.append(f"<li>Monthly Hours: {cost_record.monthly_hours}</li>")
                        debug_info.append(f"<li>Hourly Cost: {cost_record.hourly_cost}</li>")
                        debug_info.append(f"<li>Use Manual: {cost_record.use_manual}</li>")
                        debug_info.append(f"</ul>")
                else:
                    debug_info.append(f"<p><strong>{employee.name}:</strong> NO COST RECORDS</p>")

        # Check wizard lines
        debug_info.append(f"<h4>Wizard Lines:</h4>")
        for line in self.employee_cost_line_ids:
            debug_info.append(
                f"<p><strong>{line.employee_id.name}:</strong> Monthly: {line.monthly_cost}, Hourly: {line.hourly_cost}, Has Record: {line.has_cost_record}</p>")

        message = "".join(debug_info)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Employee Cost Debug',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }


class ServiceCostBreakdownLine(models.TransientModel):
    _name = 'service.cost.breakdown.line'
    _description = 'Service Cost Breakdown Line'

    wizard_id = fields.Many2one('service.cost.breakdown.wizard', required=True, ondelete='cascade')

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    monthly_cost = fields.Monetary(string='Monthly Cost', currency_field='currency_id', readonly=True)
    hourly_cost = fields.Float(string='Hourly Cost', readonly=True)
    cost_per_service_unit = fields.Monetary(string='Cost per Service Unit', currency_field='currency_id', readonly=True)
    has_cost_record = fields.Boolean(string='Has Cost Record', readonly=True)

    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)