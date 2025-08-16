from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json


class CostAllocationDashboard(http.Controller):

    @http.route('/cost_allocation/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, period_months=12):
        """Get dashboard data for cost allocation KPIs"""
        data = {}

        # Date ranges
        end_date = datetime.now().date()
        start_date = end_date - relativedelta(months=period_months)

        # Current month
        current_month_start = end_date.replace(day=1)
        prev_month_start = current_month_start - relativedelta(months=1)

        data.update({
            'period_info': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'period_months': period_months
            }
        })

        # 1. Total Cost Overview
        data['cost_overview'] = self._get_cost_overview(current_month_start, prev_month_start)

        # 2. Client Statistics
        data['client_stats'] = self._get_client_statistics(current_month_start)

        # 3. Employee Utilization
        data['employee_utilization'] = self._get_employee_utilization()

        # 4. Service Performance
        data['service_performance'] = self._get_service_performance()

        # 5. Cost Trends (last 12 months)
        data['cost_trends'] = self._get_cost_trends(start_date, end_date)

        # 6. Top Clients by Cost
        data['top_clients'] = self._get_top_clients(current_month_start)

        # 7. Pool Distribution
        data['pool_distribution'] = self._get_pool_distribution()

        # 8. Billing Summary
        data['billing_summary'] = self._get_billing_summary(current_month_start)

        return data

    def _get_cost_overview(self, current_month, prev_month):
        """Get total cost overview and comparison"""

        # Current month allocations
        current_allocations = request.env['client.cost.allocation'].search([
            ('period_date', '>=', current_month),
            ('state', 'in', ['calculated', 'confirmed'])
        ])

        # Previous month allocations
        prev_allocations = request.env['client.cost.allocation'].search([
            ('period_date', '>=', prev_month),
            ('period_date', '<', current_month),
            ('state', 'in', ['calculated', 'confirmed'])
        ])

        current_total = sum(current_allocations.mapped('total_cost'))
        prev_total = sum(prev_allocations.mapped('total_cost'))

        # Calculate change percentage
        change_percent = 0
        if prev_total > 0:
            change_percent = ((current_total - prev_total) / prev_total) * 100

        return {
            'current_total': current_total,
            'previous_total': prev_total,
            'change_percent': round(change_percent, 2),
            'change_direction': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable',
            'current_direct': sum(current_allocations.mapped('direct_cost')),
            'current_indirect': sum(current_allocations.mapped('indirect_cost')),
            'current_admin': sum(current_allocations.mapped('admin_cost')),
        }

    def _get_client_statistics(self, current_month):
        """Get client-related statistics"""

        # Total clients with services
        total_clients = request.env['res.partner'].search_count([
            ('is_company', '=', True),
            ('service_count', '>', 0)
        ])

        # Clients with active subscriptions
        active_subscriptions = request.env['res.partner'].search_count([
            ('is_company', '=', True),
            ('subscription_count', '>', 0)
        ])

        # Clients with allocations this month
        clients_with_allocations = request.env['client.cost.allocation'].search([
            ('period_date', '>=', current_month),
            ('state', 'in', ['calculated', 'confirmed'])
        ])

        allocated_clients = len(set(clients_with_allocations.mapped('client_id.id')))

        return {
            'total_clients': total_clients,
            'active_subscriptions': active_subscriptions,
            'allocated_clients': allocated_clients,
            'allocation_coverage': round((allocated_clients / max(total_clients, 1)) * 100, 1)
        }

    def _get_employee_utilization(self):
        """Get employee utilization statistics"""

        # Get latest workload data
        workloads = request.env['employee.workload'].search([
            ('period_date', '>=', datetime.now().date().replace(day=1))
        ])

        if not workloads:
            # Fallback to previous month
            prev_month = datetime.now().date().replace(day=1) - relativedelta(months=1)
            workloads = request.env['employee.workload'].search([
                ('period_date', '>=', prev_month)
            ])

        total_employees = len(workloads)
        if total_employees == 0:
            return {'total_employees': 0, 'avg_utilization': 0, 'overloaded_count': 0}

        avg_utilization = sum(workloads.mapped('utilization_percentage')) / total_employees
        overloaded_count = len(workloads.filtered('overloaded'))

        return {
            'total_employees': total_employees,
            'avg_utilization': round(avg_utilization, 1),
            'overloaded_count': overloaded_count,
            'overloaded_percent': round((overloaded_count / total_employees) * 100, 1)
        }

    def _get_service_performance(self):
        """Get service performance metrics"""

        # Active services by type
        services = request.env['client.service'].search([('status', '=', 'active')])

        # Group by service type
        service_types = {}
        for service in services:
            type_name = service.service_type_id.name
            if type_name not in service_types:
                service_types[type_name] = 0
            service_types[type_name] += 1

        # Active subscriptions
        active_subs = request.env['client.service.subscription'].search_count([
            ('state', '=', 'active')
        ])

        # Revenue from subscriptions this month
        current_month = datetime.now().date().replace(day=1)
        monthly_revenue = request.env['client.service.subscription'].search([
            ('state', '=', 'active')
        ])
        total_revenue = sum(monthly_revenue.mapped('total_amount'))

        return {
            'total_services': len(services),
            'active_subscriptions': active_subs,
            'monthly_revenue': total_revenue,
            'service_types': service_types
        }

    def _get_cost_trends(self, start_date, end_date):
        """Get cost trends over time"""

        allocations = request.env['client.cost.allocation'].search([
            ('period_date', '>=', start_date),
            ('period_date', '<=', end_date),
            ('state', 'in', ['calculated', 'confirmed'])
        ])

        # Group by month
        monthly_costs = {}
        for allocation in allocations:
            month_key = allocation.period_date.strftime('%Y-%m')
            if month_key not in monthly_costs:
                monthly_costs[month_key] = {
                    'direct': 0,
                    'indirect': 0,
                    'admin': 0,
                    'total': 0
                }

            monthly_costs[month_key]['direct'] += allocation.direct_cost
            monthly_costs[month_key]['indirect'] += allocation.indirect_cost
            monthly_costs[month_key]['admin'] += allocation.admin_cost
            monthly_costs[month_key]['total'] += allocation.total_cost

        # Convert to lists for charts
        months = sorted(monthly_costs.keys())
        direct_costs = [monthly_costs[month]['direct'] for month in months]
        indirect_costs = [monthly_costs[month]['indirect'] for month in months]
        admin_costs = [monthly_costs[month]['admin'] for month in months]
        total_costs = [monthly_costs[month]['total'] for month in months]

        return {
            'months': months,
            'direct_costs': direct_costs,
            'indirect_costs': indirect_costs,
            'admin_costs': admin_costs,
            'total_costs': total_costs
        }

    def _get_top_clients(self, current_month):
        """Get top clients by cost"""

        allocations = request.env['client.cost.allocation'].search([
            ('period_date', '>=', current_month),
            ('state', 'in', ['calculated', 'confirmed'])
        ])

        # Group by client
        client_costs = {}
        for allocation in allocations:
            client_id = allocation.client_id.id
            client_name = allocation.client_id.name

            if client_id not in client_costs:
                client_costs[client_id] = {
                    'name': client_name,
                    'total_cost': 0,
                    'service_count': allocation.client_id.service_count,
                    'cost_trend': allocation.client_id.cost_trend
                }

            client_costs[client_id]['total_cost'] += allocation.total_cost

        # Sort by total cost and take top 10
        top_clients = sorted(client_costs.values(), key=lambda x: x['total_cost'], reverse=True)[:10]

        return top_clients

    def _get_pool_distribution(self):
        """Get cost pool distribution"""

        pools = request.env['cost.pool'].search([('active', '=', True)])

        pool_data = []
        for pool in pools:
            pool_data.append({
                'name': pool.name,
                'type': pool.pool_type,
                'cost': pool.total_monthly_cost
            })

        return pool_data

    def _get_billing_summary(self, current_month):
        """Get billing and revenue summary"""

        # Active subscriptions revenue
        subscriptions = request.env['client.service.subscription'].search([
            ('state', '=', 'active')
        ])

        total_revenue = sum(subscriptions.mapped('total_amount'))
        total_cost = sum(subscriptions.mapped('total_cost') or [0])

        # Calculate margin
        margin = 0
        if total_revenue > 0:
            margin = ((total_revenue - total_cost) / total_revenue) * 100

        # Subscriptions due for invoice
        due_subscriptions = request.env['client.service.subscription'].search_count([
            ('state', '=', 'active'),
            ('next_invoice_date', '<=', datetime.now().date())
        ])

        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'margin_percent': round(margin, 1),
            'due_invoices': due_subscriptions
        }