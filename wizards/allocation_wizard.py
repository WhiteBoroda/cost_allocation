from odoo import models, fields, api
from datetime import datetime, date


class AllocationWizard(models.TransientModel):
    _name = 'allocation.wizard'
    _description = 'Cost Allocation Wizard'

    period_date = fields.Date(string='Period', required=True, default=fields.Date.today)
    client_ids = fields.Many2many('res.partner', string='Clients',
                                  domain=[('is_company', '=', True)])
    auto_calculate = fields.Boolean(string='Auto Calculate Costs', default=True)

    @api.model
    def default_get(self, fields_list):
        """Set default clients - all companies"""
        res = super().default_get(fields_list)
        if 'client_ids' in fields_list:
            clients = self.env['res.partner'].search([('is_company', '=', True)])
            res['client_ids'] = [(6, 0, clients.ids)]
        return res

    def action_create_allocations(self):
        """Create allocations for selected clients and period"""
        allocations = self.env['client.cost.allocation']

        for client in self.client_ids:
            # Check if allocation already exists
            existing = self.env['client.cost.allocation'].search([
                ('client_id', '=', client.id),
                ('period_date', '=', self.period_date)
            ])

            if not existing:
                allocation = self.env['client.cost.allocation'].create({
                    'client_id': client.id,
                    'period_date': self.period_date,
                })

                if self.auto_calculate:
                    allocation.action_calculate_costs()

                allocations |= allocation

        # Return action to show created allocations
        action = self.env.ref('cost_allocation.action_client_allocation').read()[0]
        action['domain'] = [('id', 'in', allocations.ids)]
        return action


class CostReportWizard(models.TransientModel):
    _name = 'cost.report.wizard'
    _description = 'Cost Allocation Report Wizard'

    period_from = fields.Date(string='From', required=True)
    period_to = fields.Date(string='To', required=True)
    client_ids = fields.Many2many('res.partner', string='Clients',
                                  domain=[('is_company', '=', True)])
    report_type = fields.Selection([
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('comparison', 'Period Comparison')
    ], string='Report Type', default='summary', required=True)

    @api.model
    def default_get(self, fields_list):
        """Set default period - current month"""
        res = super().default_get(fields_list)
        today = date.today()
        if 'period_from' in fields_list:
            res['period_from'] = today.replace(day=1)
        if 'period_to' in fields_list:
            res['period_to'] = today
        return res

    def action_generate_report(self):
        """Generate cost allocation report"""
        # Get allocations for the period
        domain = [
            ('period_date', '>=', self.period_from),
            ('period_date', '<=', self.period_to),
        ]

        if self.client_ids:
            domain.append(('client_id', 'in', self.client_ids.ids))

        allocations = self.env['client.cost.allocation'].search(domain)

        if not allocations:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Data',
                    'message': 'No allocations found for the selected period.',
                    'type': 'warning',
                }
            }

        if self.report_type == 'summary':
            return self._generate_summary_report(allocations)
        elif self.report_type == 'detailed':
            return self._generate_detailed_report(allocations)
        else:
            return self._generate_comparison_report(allocations)

    def _generate_summary_report(self, allocations):
        """Generate summary report"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cost Allocation Summary',
            'res_model': 'client.cost.allocation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', allocations.ids)],
            'context': {
                'search_default_group_client': 1,
                'search_default_period': 1,
            }
        }

    def _generate_detailed_report(self, allocations):
        """Generate detailed report"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detailed Cost Report',
            'res_model': 'client.cost.allocation',
            'view_mode': 'form,tree',
            'domain': [('id', 'in', allocations.ids)],
        }

    def _generate_comparison_report(self, allocations):
        """Generate comparison report"""
        # Group by client and calculate totals
        client_totals = {}
        for allocation in allocations:
            client = allocation.client_id
            if client not in client_totals:
                client_totals[client] = {
                    'direct_cost': 0,
                    'indirect_cost': 0,
                    'total_cost': 0,
                    'periods': 0
                }

            client_totals[client]['direct_cost'] += allocation.direct_cost
            client_totals[client]['indirect_cost'] += allocation.indirect_cost
            client_totals[client]['total_cost'] += allocation.total_cost
            client_totals[client]['periods'] += 1

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cost Comparison Report',
            'res_model': 'client.cost.allocation',
            'view_mode': 'pivot,graph,tree',
            'domain': [('id', 'in', allocations.ids)],
            'context': {
                'search_default_group_client': 1,
                'pivot_measures': ['direct_cost', 'indirect_cost', 'total_cost'],
                'pivot_column_groupby': ['period_date:month'],
                'pivot_row_groupby': ['client_id'],
            }
        }