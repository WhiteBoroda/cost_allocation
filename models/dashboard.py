from odoo import models, fields, api


class CostAllocationDashboard(models.Model):
    _name = 'cost.allocation.dashboard'
    _description = 'Cost Allocation Dashboard'
    _rec_name = 'name'

    name = fields.Char(string='Dashboard Name', default='Cost Allocation Dashboard')

    @api.model
    def get_dashboard_data(self, period_months=12):
        """API method to get dashboard data - calls controller"""
        # This could also contain direct data processing
        # For now, we rely on the controller for data processing
        return True

    @api.model
    def get_quick_stats(self):
        """Get quick statistics for dashboard widgets"""

        # Current active entities count
        stats = {
            'total_employees': self.env['cost.employee'].search_count([('active', '=', True)]),
            'total_pools': self.env['cost.pool'].search_count([('active', '=', True)]),
            'total_drivers': self.env['cost.driver'].search_count([('active', '=', True)]),
            'total_services': self.env['client.service'].search_count([('status', '=', 'active')]),
            'active_subscriptions': self.env['client.service.subscription'].search_count([('state', '=', 'active')]),
            'pending_allocations': self.env['client.cost.allocation'].search_count([('state', '=', 'draft')])
        }

        return stats