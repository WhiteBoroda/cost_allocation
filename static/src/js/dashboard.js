/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CostAllocationDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: {},
            period: 12,
            chartsLoaded: false
        });

        onMounted(() => {
            this.loadDashboardData();
            this.setupEventListeners();
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;

            const data = await this.rpc('/cost_allocation/dashboard_data', {
                period_months: this.state.period
            });

            this.state.data = data;
            this.state.loading = false;

            // Update UI
            this.updateKPICards(data);
            this.updateTopClients(data.top_clients);
            this.renderCharts(data);

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.notification.add('Failed to load dashboard data', { type: 'danger' });
            this.state.loading = false;
        }
    }

    updateKPICards(data) {
        const { cost_overview, client_stats, employee_utilization, billing_summary } = data;

        // Total Cost
        const totalCostEl = document.getElementById('total_cost');
        if (totalCostEl && cost_overview) {
            totalCostEl.textContent = this.formatCurrency(cost_overview.current_total);

            const changeEl = document.getElementById('cost_change');
            if (changeEl) {
                const changePercent = cost_overview.change_percent;
                const direction = cost_overview.change_direction;

                changeEl.textContent = `${changePercent > 0 ? '+' : ''}${changePercent}% vs last month`;
                changeEl.className = `change-indicator text-${direction === 'up' ? 'warning' : direction === 'down' ? 'success' : 'muted'}`;
            }
        }

        // Revenue
        const revenueEl = document.getElementById('total_revenue');
        if (revenueEl && billing_summary) {
            revenueEl.textContent = this.formatCurrency(billing_summary.total_revenue);

            const marginEl = document.getElementById('margin_info');
            if (marginEl) {
                marginEl.textContent = `Margin: ${billing_summary.margin_percent}%`;
            }
        }

        // Clients
        const clientsEl = document.getElementById('total_clients');
        if (clientsEl && client_stats) {
            clientsEl.textContent = client_stats.total_clients.toString();

            const coverageEl = document.getElementById('allocation_coverage');
            if (coverageEl) {
                coverageEl.textContent = `Coverage: ${client_stats.allocation_coverage}%`;
            }
        }

        // Team Utilization
        const utilizationEl = document.getElementById('avg_utilization');
        if (utilizationEl && employee_utilization) {
            utilizationEl.textContent = `${employee_utilization.avg_utilization}%`;

            const overloadedEl = document.getElementById('overloaded_info');
            if (overloadedEl) {
                overloadedEl.textContent = `Overloaded: ${employee_utilization.overloaded_count}`;
            }
        }

        // Service Stats
        const servicesEl = document.getElementById('total_services');
        if (servicesEl && data.service_performance) {
            servicesEl.textContent = data.service_performance.total_services.toString();
        }

        const subscriptionsEl = document.getElementById('active_subscriptions');
        if (subscriptionsEl && data.service_performance) {
            subscriptionsEl.textContent = data.service_performance.active_subscriptions.toString();
        }

        // Billing Status
        const dueInvoicesEl = document.getElementById('due_invoices');
        if (dueInvoicesEl && billing_summary) {
            dueInvoicesEl.textContent = billing_summary.due_invoices.toString();
        }
    }

    updateTopClients(topClients) {
        const listEl = document.getElementById('top_clients_list');
        if (!listEl || !topClients) return;

        let html = '';
        topClients.forEach((client, index) => {
            const trendIcon = this.getTrendIcon(client.cost_trend);
            const costFormatted = this.formatCurrency(client.total_cost);

            html += `
                <div class="d-flex justify-content-between align-items-center mb-2 p-2 border-bottom">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-primary me-2">${index + 1}</span>
                        <div>
                            <strong>${client.name}</strong>
                            <br><small class="text-muted">${client.service_count} services</small>
                        </div>
                    </div>
                    <div class="text-end">
                        <strong>${costFormatted}</strong>
                        <br><small class="text-muted">${trendIcon}</small>
                    </div>
                </div>
            `;
        });

        listEl.innerHTML = html;
    }

    renderCharts(data) {
        // Load Chart.js if not already loaded
        if (typeof Chart === 'undefined') {
            this.loadChartJS().then(() => {
                this.createCharts(data);
            });
        } else {
            this.createCharts(data);
        }
    }

    async loadChartJS() {
        return new Promise((resolve) => {
            if (document.getElementById('chartjs-script')) {
                resolve();
                return;
            }

            const script = document.createElement('script');
            script.id = 'chartjs-script';
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js';
            script.onload = resolve;
            document.head.appendChild(script);
        });
    }

    createCharts(data) {
        this.createCostTrendsChart(data.cost_trends);
        this.createPoolDistributionChart(data.pool_distribution);
        this.state.chartsLoaded = true;
    }

    createCostTrendsChart(trendData) {
        const ctx = document.getElementById('costTrendsChart');
        if (!ctx || !trendData) return;

        // Format month labels
        const labels = trendData.months.map(month => {
            const [year, monthNum] = month.split('-');
            const date = new Date(year, monthNum - 1);
            return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
        });

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Cost',
                    data: trendData.total_costs,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => this.formatCurrency(value, true)
                        }
                    }
                },
                elements: {
                    point: {
                        radius: 4,
                        hoverRadius: 6
                    }
                }
            }
        });
    }

    createPoolDistributionChart(poolData) {
        const ctx = document.getElementById('poolDistributionChart');
        if (!ctx || !poolData) return;

        const labels = poolData.map(pool => pool.name);
        const costs = poolData.map(pool => pool.cost);
        const colors = this.generateColors(poolData.length);

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: costs,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = this.formatCurrency(context.raw);
                                return `${context.label}: ${value}`;
                            }
                        }
                    }
                }
            }
        });
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh_dashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboardData();
            });
        }

        // Period selection
        document.querySelectorAll('.period-select').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const period = parseInt(e.target.dataset.period);
                this.changePeriod(period);
            });
        });

        // Quick actions
        const createAllocationBtn = document.getElementById('create_allocation');
        if (createAllocationBtn) {
            createAllocationBtn.addEventListener('click', () => {
                this.action.doAction('cost_allocation.action_allocation_wizard');
            });
        }

        const generateInvoicesBtn = document.getElementById('generate_invoices');
        if (generateInvoicesBtn) {
            generateInvoicesBtn.addEventListener('click', () => {
                this.action.doAction('cost_allocation.action_client_service_subscription');
            });
        }
    }

    changePeriod(newPeriod) {
        this.state.period = newPeriod;

        // Update active button
        document.querySelectorAll('.period-select').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-period="${newPeriod}"]`).classList.add('active');

        // Reload data
        this.loadDashboardData();
    }

    formatCurrency(amount, short = false) {
        if (!amount && amount !== 0) return '-';

        const formatted = new Intl.NumberFormat('uk-UA', {
            style: 'currency',
            currency: 'UAH',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);

        if (short && amount >= 1000) {
            if (amount >= 1000000) {
                return (amount / 1000000).toFixed(1) + 'M ₴';
            } else if (amount >= 1000) {
                return (amount / 1000).toFixed(0) + 'K ₴';
            }
        }

        return formatted;
    }

    getTrendIcon(trend) {
        const icons = {
            'up': '<i class="fa fa-arrow-up text-danger"></i>',
            'down': '<i class="fa fa-arrow-down text-success"></i>',
            'stable': '<i class="fa fa-minus text-muted"></i>',
            'new': '<i class="fa fa-star text-info"></i>'
        };

        return icons[trend] || icons['stable'];
    }

    generateColors(count) {
        const colors = [
            '#007bff', '#28a745', '#ffc107', '#dc3545', '#6f42c1',
            '#fd7e14', '#20c997', '#6c757d', '#e83e8c', '#17a2b8'
        ];

        return colors.slice(0, count);
    }

    cleanup() {
        // Clean up event listeners if needed
        document.querySelectorAll('.period-select').forEach(btn => {
            btn.removeEventListener('click', this.changePeriod);
        });
    }
}

// Register the component
CostAllocationDashboard.template = "cost_allocation.Dashboard";

registry.category("actions").add("cost_allocation_dashboard", CostAllocationDashboard);