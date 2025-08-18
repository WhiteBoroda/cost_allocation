from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class CostAllocationDashboard(http.Controller):

    @http.route('/cost_allocation/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, period_months=12):
        """Get dashboard data for cost allocation KPIs"""
        try:
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

            # Get data with error handling
            data['cost_overview'] = self._get_cost_overview(current_month_start, prev_month_start)
            data['client_stats'] = self._get_client_statistics(current_month_start)
            data['employee_utilization'] = self._get_employee_utilization()
            data['service_performance'] = self._get_service_performance()
            data['cost_trends'] = self._get_cost_trends(start_date, end_date)
            data['top_clients'] = self._get_top_clients(current_month_start)
            data['pool_distribution'] = self._get_pool_distribution()
            data['billing_summary'] = self._get_billing_summary(current_month_start)

            return data

        except Exception as e:
            _logger.error(f"Dashboard data error: {str(e)}")
            # Return safe fallback data
            return self._get_fallback_data(period_months)

    def _get_fallback_data(self, period_months):
        """Return safe fallback data when main data fails"""
        return {
            'period_info': {
                'start_date': (datetime.now().date() - relativedelta(months=period_months)).strftime('%Y-%m-%d'),
                'end_date': datetime.now().date().strftime('%Y-%m-%d'),
                'period_months': period_months
            },
            'cost_overview': {
                'current_total': 0,
                'previous_total': 0,
                'change_percent': 0,
                'change_direction': 'stable',
                'current_direct': 0,
                'current_indirect': 0,
                'current_admin': 0,
            },
            'client_stats': {
                'total_clients': 0,
                'active_subscriptions': 0,
                'allocated_clients': 0,
                'allocation_coverage': 0
            },
            'employee_utilization': {
                'total_employees': 0,
                'avg_utilization': 0,
                'overloaded_count': 0,
                'overloaded_percent': 0
            },
            'service_performance': {
                'total_services': 0,
                'active_subscriptions': 0,
                'monthly_revenue': 0,
                'service_types': {}
            },
            'cost_trends': {
                'months': [],
                'direct_costs': [],
                'indirect_costs': [],
                'admin_costs': [],
                'total_costs': []
            },
            'top_clients': [],
            'pool_distribution': [],
            'billing_summary': {
                'total_revenue': 0,
                'total_cost': 0,
                'margin_percent': 0,
                'due_invoices': 0
            }
        }

    def _get_cost_overview(self, current_month, prev_month):
        """Get total cost overview and comparison"""
        try:
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

            current_total = sum(current_allocations.mapped('total_cost')) if current_allocations else 0
            prev_total = sum(prev_allocations.mapped('total_cost')) if prev_allocations else 0

            # Calculate change percentage
            change_percent = 0
            if prev_total > 0:
                change_percent = ((current_total - prev_total) / prev_total) * 100

            return {
                'current_total': current_total,
                'previous_total': prev_total,
                'change_percent': round(change_percent, 2),
                'change_direction': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable',
                'current_direct': sum(current_allocations.mapped('direct_cost')) if current_allocations else 0,
                'current_indirect': sum(current_allocations.mapped('indirect_cost')) if current_allocations else 0,
                'current_admin': sum(current_allocations.mapped('admin_cost')) if current_allocations else 0,
            }
        except Exception as e:
            _logger.error(f"Cost overview error: {str(e)}")
            return {
                'current_total': 0, 'previous_total': 0, 'change_percent': 0,
                'change_direction': 'stable', 'current_direct': 0,
                'current_indirect': 0, 'current_admin': 0,
            }

    def _get_client_statistics(self, current_month):
        """Get client-related statistics"""
        try:
            # Total clients with services
            total_clients = request.env['res.partner'].search_count([
                ('is_company', '=', True),
                ('service_count', '>', 0)
            ])

            # If no service_count field exists, use alternative
            if total_clients == 0:
                total_clients = request.env['res.partner'].search_count([
                    ('is_company', '=', True)
                ])

            # Active subscriptions
            active_subscriptions = 0
            if hasattr(request.env['res.partner'], 'subscription_count'):
                active_subscriptions = request.env['res.partner'].search_count([
                    ('is_company', '=', True),
                    ('subscription_count', '>', 0)
                ])

            # Clients with allocations this month
            clients_with_allocations = request.env['client.cost.allocation'].search([
                ('period_date', '>=', current_month),
                ('state', 'in', ['calculated', 'confirmed'])
            ])

            allocated_clients = len(
                set(clients_with_allocations.mapped('client_id.id'))) if clients_with_allocations else 0

            return {
                'total_clients': total_clients,
                'active_subscriptions': active_subscriptions,
                'allocated_clients': allocated_clients,
                'allocation_coverage': round((allocated_clients / max(total_clients, 1)) * 100, 1)
            }
        except Exception as e:
            _logger.error(f"Client statistics error: {str(e)}")
            return {
                'total_clients': 0, 'active_subscriptions': 0,
                'allocated_clients': 0, 'allocation_coverage': 0
            }

    def _get_employee_utilization(self):
        """Get employee utilization statistics"""
        try:
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
                # Fallback to employee count
                total_employees = request.env['cost.employee'].search_count([('active', '=', True)])

            avg_utilization = 0
            overloaded_count = 0
            if workloads:
                avg_utilization = sum(workloads.mapped('utilization_percentage')) / total_employees
                overloaded_count = len(workloads.filtered('overloaded'))

            return {
                'total_employees': total_employees,
                'avg_utilization': round(avg_utilization, 1),
                'overloaded_count': overloaded_count,
                'overloaded_percent': round((overloaded_count / max(total_employees, 1)) * 100, 1)
            }
        except Exception as e:
            _logger.error(f"Employee utilization error: {str(e)}")
            return {
                'total_employees': 0, 'avg_utilization': 0,
                'overloaded_count': 0, 'overloaded_percent': 0
            }

    def _get_service_performance(self):
        """Get service performance metrics"""
        try:
            # Active services by type
            services = request.env['client.service'].search([('status', '=', 'active')])

            # Group by service type
            service_types = {}
            for service in services:
                if hasattr(service, 'service_type_id') and service.service_type_id:
                    type_name = service.service_type_id.name
                elif hasattr(service, 'service_id') and service.service_id:
                    type_name = service.service_id.name
                else:
                    type_name = 'Other'

                if type_name not in service_types:
                    service_types[type_name] = 0
                service_types[type_name] += 1

            # Active subscriptions
            active_subs = 0
            try:
                active_subs = request.env['client.service.subscription'].search_count([
                    ('state', '=', 'active')
                ])
            except:
                pass

            # Revenue from subscriptions this month
            total_revenue = 0
            try:
                monthly_revenue = request.env['client.service.subscription'].search([
                    ('state', '=', 'active')
                ])
                total_revenue = sum(monthly_revenue.mapped('total_amount'))
            except:
                pass

            return {
                'total_services': len(services),
                'active_subscriptions': active_subs,
                'monthly_revenue': total_revenue,
                'service_types': service_types
            }
        except Exception as e:
            _logger.error(f"Service performance error: {str(e)}")
            return {
                'total_services': 0, 'active_subscriptions': 0,
                'monthly_revenue': 0, 'service_types': {}
            }

    def _get_cost_trends(self, start_date, end_date):
        """Get cost trends over time"""
        try:
            allocations = request.env['client.cost.allocation'].search([
                ('period_date', '>=', start_date),
                ('period_date', '<=', end_date),
                ('state', 'in', ['calculated', 'confirmed'])
            ])

            if not allocations:
                return {
                    'months': [], 'direct_costs': [], 'indirect_costs': [],
                    'admin_costs': [], 'total_costs': []
                }

            # Group by month
            monthly_costs = {}
            for allocation in allocations:
                month_key = allocation.period_date.strftime('%Y-%m')
                if month_key not in monthly_costs:
                    monthly_costs[month_key] = {
                        'direct': 0, 'indirect': 0, 'admin': 0, 'total': 0
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
        except Exception as e:
            _logger.error(f"Cost trends error: {str(e)}")
            return {
                'months': [], 'direct_costs': [], 'indirect_costs': [],
                'admin_costs': [], 'total_costs': []
            }

    def _get_top_clients(self, current_month):
        """Get top clients by cost"""
        try:
            allocations = request.env['client.cost.allocation'].search([
                ('period_date', '>=', current_month),
                ('state', 'in', ['calculated', 'confirmed'])
            ])

            if not allocations:
                return []

            # Group by client
            client_costs = {}
            for allocation in allocations:
                client_id = allocation.client_id.id
                client_name = allocation.client_id.name

                if client_id not in client_costs:
                    service_count = 0
                    cost_trend = 'new'

                    # Try to get service count
                    try:
                        service_count = allocation.client_id.service_count or 0
                    except:
                        service_count = 0

                    # Try to get cost trend
                    try:
                        cost_trend = allocation.client_id.cost_trend or 'new'
                    except:
                        cost_trend = 'new'

                    client_costs[client_id] = {
                        'name': client_name,
                        'total_cost': 0,
                        'service_count': service_count,
                        'cost_trend': cost_trend
                    }

                client_costs[client_id]['total_cost'] += allocation.total_cost

            # Sort by total cost and take top 10
            top_clients = sorted(client_costs.values(), key=lambda x: x['total_cost'], reverse=True)[:10]
            return top_clients

        except Exception as e:
            _logger.error(f"Top clients error: {str(e)}")
            return []

    def _get_pool_distribution(self):
        """Get cost pool distribution"""
        try:
            pools = request.env['cost.pool'].search([('active', '=', True)])

            pool_data = []
            for pool in pools:
                pool_data.append({
                    'name': pool.name,
                    'type': pool.pool_type,
                    'cost': pool.total_monthly_cost
                })

            return pool_data
        except Exception as e:
            _logger.error(f"Pool distribution error: {str(e)}")
            return []

    def _get_billing_summary(self, current_month):
        """Get billing and revenue summary"""
        try:
            # Active subscriptions revenue
            total_revenue = 0
            total_cost = 0
            due_subscriptions = 0

            try:
                subscriptions = request.env['client.service.subscription'].search([
                    ('state', '=', 'active')
                ])
                total_revenue = sum(subscriptions.mapped('total_amount'))

                # Try to get total cost
                try:
                    total_cost = sum(subscriptions.mapped('total_cost'))
                except:
                    total_cost = 0

                # Subscriptions due for invoice
                due_subscriptions = request.env['client.service.subscription'].search_count([
                    ('state', '=', 'active'),
                    ('next_invoice_date', '<=', datetime.now().date())
                ])
            except:
                pass

            # Calculate margin
            margin = 0
            if total_revenue > 0 and total_cost > 0:
                margin = ((total_revenue - total_cost) / total_revenue) * 100

            return {
                'total_revenue': total_revenue,
                'total_cost': total_cost,
                'margin_percent': round(margin, 1),
                'due_invoices': due_subscriptions
            }
        except Exception as e:
            _logger.error(f"Billing summary error: {str(e)}")
            return {
                'total_revenue': 0, 'total_cost': 0,
                'margin_percent': 0, 'due_invoices': 0
            }