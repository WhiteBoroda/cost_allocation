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

    # Cost breakdown
    base_cost = fields.Monetary(related='service_catalog_id.base_cost', readonly=True)
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
    has_missing_records = fields.Boolean(
        string='Has Missing Cost Records',
        compute='_compute_missing_records',
        readonly=True
    )
    @api.depends('employee_cost_line_ids.has_cost_record')
    def _compute_missing_records(self):
        for wizard in self:
            wizard.has_missing_records = any(not line.has_cost_record for line in wizard.employee_cost_line_ids)

    @api.depends('responsible_team_ids')
    def _compute_team_stats(self):
        for wizard in self:
            wizard.team_count = len(wizard.responsible_team_ids)

            # Calculate average hourly cost
            if wizard.responsible_team_ids:
                employee_costs = self.env['cost.employee'].search([
                    ('employee_id', 'in', wizard.responsible_team_ids.ids),
                    ('active', '=', True)
                ])

                if employee_costs:
                    total_hourly = sum(employee_costs.mapped('hourly_cost'))
                    wizard.average_hourly_cost = total_hourly / len(employee_costs)
                else:
                    wizard.average_hourly_cost = 0.0
            else:
                wizard.average_hourly_cost = 0.0

    @api.model
    def default_get(self, fields_list):
        """Pre-populate employee cost lines"""
        values = super().default_get(fields_list)

        if 'service_catalog_id' in self._context:
            service_catalog = self.env['service.catalog'].browse(self._context['service_catalog_id'])
            values['service_catalog_id'] = service_catalog.id

            # Create employee cost lines
            if service_catalog.service_type_id.default_responsible_ids:
                employee_lines = []
                employees = service_catalog.service_type_id.default_responsible_ids

                for employee in employees:
                    # Find employee cost record
                    emp_cost = self.env['cost.employee'].search([
                        ('employee_id', '=', employee.id),
                        ('active', '=', True)
                    ], limit=1)

                    if emp_cost:
                        employee_lines.append((0, 0, {
                            'employee_id': employee.id,
                            'monthly_cost': emp_cost.monthly_total_cost,
                            'hourly_cost': emp_cost.hourly_cost,
                            'cost_per_service_unit': emp_cost.hourly_cost * service_catalog.support_hours_per_unit,
                            'has_cost_record': True
                        }))
                    else:
                        employee_lines.append((0, 0, {
                            'employee_id': employee.id,
                            'monthly_cost': 0.0,
                            'hourly_cost': 0.0,
                            'cost_per_service_unit': 0.0,
                            'has_cost_record': False
                        }))

                values['employee_cost_line_ids'] = employee_lines

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
            # Create basic cost record
            self.env['cost.employee'].create({
                'employee_id': line.employee_id.id,
                'monthly_salary': 5000.0,  # Default value - user needs to update
                'use_manual': True,
                'manual_monthly_hours': 168.0,
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