/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState, xml, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CostAllocationDashboard extends Component {
    static template = xml`<div class="o_cost_dashboard_container" t-ref="dashboardContainer"></div>`;

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dashboardRef = useRef("dashboardContainer");

        this.state = useState({
            loading: true,
            data: {},
            period: 12,
            chartsLoaded: false,
            error: null
        });

        onMounted(() => {
            this.renderDashboard();
            this.loadDashboardData();
            this.setupEventListeners();
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    renderDashboard() {
        // Create dashboard HTML structure in the template container
        const container = this.dashboardRef.el;
        if (container) {
            container.innerHTML = this.getDashboardHTML();
        } else {
            console.error('Dashboard container not found');
        }
    }

    getDashboardHTML() {
        return `
            <div class="o_cost_allocation_dashboard">
                <div class="container-fluid o_cost_dashboard">
                    <!-- Header -->
                    <div class="row mb-3">
                        <div class="col-12">
                            <div class="d-flex justify-content-between align-items-center">
                                <h2 class="mb-0">
                                    <i class="fa fa-dashboard text-primary"></i>
                                    Cost Allocation Dashboard
                                </h2>
                                <div class="btn-group">
                                    <button type="button" class="btn btn-outline-primary btn-sm" id="refresh_dashboard">
                                        <i class="fa fa-refresh"></i> Refresh
                                    </button>
                                    <button type="button" class="btn btn-outline-secondary btn-sm dropdown-toggle" data-bs-toggle="dropdown">
                                        <i class="fa fa-calendar"></i> Period
                                    </button>
                                    <ul class="dropdown-menu">
                                        <li><a class="dropdown-item period-select" data-period="3">Last 3 months</a></li>
                                        <li><a class="dropdown-item period-select" data-period="6">Last 6 months</a></li>
                                        <li><a class="dropdown-item period-select active" data-period="12">Last 12 months</a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Error Alert -->
                    <div class="row mb-3" id="error_alert" style="display: none;">
                        <div class="col-12">
                            <div class="alert alert-warning alert-dismissible fade show" role="alert">
                                <strong>Loading Error:</strong> <span id="error_message"></span>
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        </div>
                    </div>

                    <!-- KPI Cards -->
                    <div class="row mb-4">
                        <div class="col-lg-3 col-md-6 mb-3">
                            <div class="card bg-primary text-white h-100">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <h6 class="card-title text-uppercase mb-1">Total Monthly Cost</h6>
                                            <h3 class="mb-0" id="total_cost">-</h3>
                                            <small id="cost_change" class="change-indicator">-</small>
                                        </div>
                                        <div class="align-self-center">
                                            <i class="fa fa-calculator fa-2x opacity-75"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-3 col-md-6 mb-3">
                            <div class="card bg-success text-white h-100">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <h6 class="card-title text-uppercase mb-1">Monthly Revenue</h6>
                                            <h3 class="mb-0" id="total_revenue">-</h3>
                                            <small id="margin_info" class="change-indicator">-</small>
                                        </div>
                                        <div class="align-self-center">
                                            <i class="fa fa-money fa-2x opacity-75"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-3 col-md-6 mb-3">
                            <div class="card bg-info text-white h-100">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <h6 class="card-title text-uppercase mb-1">Active Clients</h6>
                                            <h3 class="mb-0" id="total_clients">-</h3>
                                            <small id="allocation_coverage">Coverage: -%</small>
                                        </div>
                                        <div class="align-self-center">
                                            <i class="fa fa-users fa-2x opacity-75"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-3 col-md-6 mb-3">
                            <div class="card bg-warning text-white h-100">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <h6 class="card-title text-uppercase mb-1">Team Utilization</h6>
                                            <h3 class="mb-0" id="avg_utilization">-</h3>
                                            <small id="overloaded_info">Overloaded: -</small>
                                        </div>
                                        <div class="align-self-center">
                                            <i class="fa fa-clock-o fa-2x opacity-75"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Charts Row -->
                    <div class="row mb-4">
                        <div class="col-lg-8 mb-3">
                            <div class="card h-100">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <h5 class="mb-0">
                                        <i class="fa fa-line-chart text-primary"></i>
                                        Cost Trends
                                    </h5>
                                    <div class="btn-group btn-group-sm">
                                        <button type="button" class="btn btn-outline-primary active" id="chart_total">Total</button>
                                        <button type="button" class="btn btn-outline-secondary" id="chart_breakdown">Breakdown</button>
                                    </div>
                                </div>
                                <div class="card-body">
                                    <canvas id="costTrendsChart" style="height: 300px;"></canvas>
                                    <div id="trends_no_data" style="display: none;" class="text-center text-muted py-5">
                                        <i class="fa fa-chart-line fa-3x mb-3"></i>
                                        <p>No cost data available for the selected period</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-4 mb-3">
                            <div class="card h-100">
                                <div class="card-header">
                                    <h5 class="mb-0">
                                        <i class="fa fa-pie-chart text-success"></i>
                                        Cost Pool Distribution
                                    </h5>
                                </div>
                                <div class="card-body">
                                    <canvas id="poolDistributionChart" style="height: 300px;"></canvas>
                                    <div id="pools_no_data" style="display: none;" class="text-center text-muted py-5">
                                        <i class="fa fa-pie-chart fa-3x mb-3"></i>
                                        <p>No cost pools configured</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Details Row -->
                    <div class="row">
                        <div class="col-lg-6 mb-3">
                            <div class="card h-100">
                                <div class="card-header">
                                    <h5 class="mb-0">
                                        <i class="fa fa-trophy text-warning"></i>
                                        Top Clients by Cost
                                    </h5>
                                </div>
                                <div class="card-body">
                                    <div id="top_clients_list">
                                        <div class="text-center text-muted">
                                            <i class="fa fa-spinner fa-spin"></i> Loading...
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-6 mb-3">
                            <div class="card h-100">
                                <div class="card-header">
                                    <h5 class="mb-0">
                                        <i class="fa fa-cogs text-info"></i>
                                        Quick Actions & Stats
                                    </h5>
                                </div>
                                <div class="card-body">
                                    <div class="mb-3">
                                        <h6 class="text-muted mb-2">Quick Actions</h6>
                                        <div class="d-grid gap-2">
                                            <button type="button" class="btn btn-outline-primary btn-sm" id="create_allocation">
                                                <i class="fa fa-plus"></i> Create Allocation
                                            </button>
                                            <button type="button" class="btn btn-outline-success btn-sm" id="generate_invoices">
                                                <i class="fa fa-file-text"></i> Generate Invoices
                                            </button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <h6 class="text-muted mb-2">Service Overview</h6>
                                        <div class="row text-center">
                                            <div class="col-6">
                                                <div class="border rounded p-2">
                                                    <strong id="total_services" class="d-block h5 mb-0">-</strong>
                                                    <small class="text-muted">Active Services</small>
                                                </div>
                                            </div>
                                            <div class="col-6">
                                                <div class="border rounded p-2">
                                                    <strong id="active_subscriptions" class="d-block h5 mb-0">-</strong>
                                                    <small class="text-muted">Subscriptions</small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div>
                                        <h6 class="text-muted mb-2">Billing Status</h6>
                                        <div class="alert alert-info py-2 mb-0">
                                            <small>
                                                <strong id="due_invoices">-</strong> subscriptions due for invoice
                                            </small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;
            this.state.error = null;

            console.log('Loading dashboard data...');

            const data = await this.rpc('/cost_allocation/dashboard_data', {
                period_months: this.state.period
            });

            console.log('Dashboard data loaded:', data);

            this.state.data = data;
            this.state.loading = false;

            // Hide error alert if it was shown
            const errorAlert = document.getElementById('error_alert');
            if (errorAlert) {
                errorAlert.style.display = 'none';
            }

            // Update UI
            this.updateKPICards(data);
            this.updateTopClients(data.top_clients || []);
            this.renderCharts(data);

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.loading = false;
            this.state.error = error.message || 'Unknown error';

            // Show error in UI
            this.showError('Failed to load dashboard data: ' + (error.message || 'Network error'));

            // Load fallback data
            this.loadFallbackData();
        }
    }

    showError(message) {
        const errorAlert = document.getElementById('error_alert');
        const errorMessage = document.getElementById('error_message');

        if (errorAlert && errorMessage) {
            errorMessage.textContent = message;
            errorAlert.style.display = 'block';
        }

        // Also show notification
        this.notification.add(message, { type: 'danger' });
    }

    loadFallbackData() {
        // Load basic data to prevent empty dashboard
        const fallbackData = {
            cost_overview: { current_total: 0, previous_total: 0, change_percent: 0 },
            client_stats: { total_clients: 0, active_subscriptions: 0, allocated_clients: 0, allocation_coverage: 0 },
            employee_utilization: { total_employees: 0, avg_utilization: 0, overloaded_count: 0 },
            billing_summary: { total_revenue: 0, total_cost: 0, margin_percent: 0, due_invoices: 0 },
            service_performance: { total_services: 0, active_subscriptions: 0 },
            top_clients: [],
            cost_trends: { months: [], total_costs: [] },
            pool_distribution: []
        };

        this.updateKPICards(fallbackData);
        this.updateTopClients([]);
    }

    updateKPICards(data) {
        if (!data) return;

        const {
            cost_overview = {},
            client_stats = {},
            employee_utilization = {},
            billing_summary = {},
            service_performance = {}
        } = data;

        // Total Cost
        const totalCostEl = document.getElementById('total_cost');
        if (totalCostEl) {
            totalCostEl.textContent = this.formatCurrency(cost_overview.current_total || 0);

            const changeEl = document.getElementById('cost_change');
            if (changeEl) {
                const change_percent = cost_overview.change_percent || 0;
                const change_direction = cost_overview.change_direction || 'stable';

                changeEl.textContent = `${change_percent > 0 ? '+' : ''}${change_percent}% vs last month`;
                changeEl.className = `change-indicator text-${change_direction === 'up' ? 'warning' : change_direction === 'down' ? 'success' : 'muted'}`;
            }
        }

        // Revenue
        const revenueEl = document.getElementById('total_revenue');
        if (revenueEl) {
            revenueEl.textContent = this.formatCurrency(billing_summary.total_revenue || 0);

            const marginEl = document.getElementById('margin_info');
            if (marginEl) {
                marginEl.textContent = `Margin: ${billing_summary.margin_percent || 0}%`;
            }
        }

        // Clients
        const clientsEl = document.getElementById('total_clients');
        if (clientsEl) {
            clientsEl.textContent = (client_stats.total_clients || 0).toString();

            const coverageEl = document.getElementById('allocation_coverage');
            if (coverageEl) {
                coverageEl.textContent = `Coverage: ${client_stats.allocation_coverage || 0}%`;
            }
        }

        // Team Utilization
        const utilizationEl = document.getElementById('avg_utilization');
        if (utilizationEl) {
            utilizationEl.textContent = `${employee_utilization.avg_utilization || 0}%`;

            const overloadedEl = document.getElementById('overloaded_info');
            if (overloadedEl) {
                overloadedEl.textContent = `Overloaded: ${employee_utilization.overloaded_count || 0}`;
            }
        }

        // Service Stats
        const servicesEl = document.getElementById('total_services');
        if (servicesEl) {
            servicesEl.textContent = (service_performance.total_services || 0).toString();
        }

        const subscriptionsEl = document.getElementById('active_subscriptions');
        if (subscriptionsEl) {
            subscriptionsEl.textContent = (service_performance.active_subscriptions || 0).toString();
        }

        // Billing Status
        const dueInvoicesEl = document.getElementById('due_invoices');
        if (dueInvoicesEl) {
            dueInvoicesEl.textContent = (billing_summary.due_invoices || 0).toString();
        }
    }

    updateTopClients(topClients) {
        const listEl = document.getElementById('top_clients_list');
        if (!listEl) return;

        if (!topClients || !Array.isArray(topClients) || topClients.length === 0) {
            listEl.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fa fa-users fa-3x mb-3"></i>
                    <p>No client cost data available</p>
                    <small>Create cost allocations to see top clients</small>
                </div>
            `;
            return;
        }

        let html = '';
        topClients.forEach((client, index) => {
            const trendIcon = this.getTrendIcon(client.cost_trend || 'stable');
            const costFormatted = this.formatCurrency(client.total_cost || 0);
            const serviceCount = client.service_count || 0;

            html += `
                <div class="d-flex justify-content-between align-items-center mb-2 p-2 border-bottom">
                    <div class="d-flex align-items-center">
                        <span class="badge bg-primary me-2">${index + 1}</span>
                        <div>
                            <strong>${client.name || 'Unknown Client'}</strong>
                            <br><small class="text-muted">${serviceCount} services</small>
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
        if (!data) return;

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
            script.onerror = () => {
                console.error('Failed to load Chart.js');
                resolve(); // Don't block the dashboard
            };
            document.head.appendChild(script);
        });
    }

    createCharts(data) {
        const { cost_trends, pool_distribution } = data;

        if (cost_trends && cost_trends.months && cost_trends.months.length > 0) {
            this.createCostTrendsChart(cost_trends);
        } else {
            document.getElementById('trends_no_data').style.display = 'block';
        }

        if (pool_distribution && pool_distribution.length > 0) {
            this.createPoolDistributionChart(pool_distribution);
        } else {
            document.getElementById('pools_no_data').style.display = 'block';
        }

        this.state.chartsLoaded = true;
    }

    createCostTrendsChart(trendData) {
        const ctx = document.getElementById('costTrendsChart');
        if (!ctx || !trendData || !trendData.months || !trendData.total_costs) return;

        try {
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
        } catch (error) {
            console.error('Error creating cost trends chart:', error);
        }
    }

    createPoolDistributionChart(poolData) {
        const ctx = document.getElementById('poolDistributionChart');
        if (!ctx || !poolData || !Array.isArray(poolData) || poolData.length === 0) return;

        try {
            const labels = poolData.map(pool => pool.name || 'Unknown');
            const costs = poolData.map(pool => pool.cost || 0);
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
        } catch (error) {
            console.error('Error creating pool distribution chart:', error);
        }
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh_dashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboardData().catch(console.error);
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
                this.action.doAction('cost_allocation.action_allocation_wizard').catch(console.error);
            });
        }

        const generateInvoicesBtn = document.getElementById('generate_invoices');
        if (generateInvoicesBtn) {
            generateInvoicesBtn.addEventListener('click', () => {
                this.action.doAction('cost_allocation.action_client_service_subscription').catch(console.error);
            });
        }
    }

    changePeriod(newPeriod) {
        this.state.period = newPeriod;

        // Update active button
        document.querySelectorAll('.period-select').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`[data-period="${newPeriod}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }

        // Reload data
        this.loadDashboardData().catch(console.error);
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
registry.category("actions").add("cost_allocation_dashboard", CostAllocationDashboard);