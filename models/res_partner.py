from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Service statistics - ИСПРАВЛЕНО: добавил store=True для возможности поиска
    service_count = fields.Integer(string='Active Services', compute='_compute_service_stats', store=True)
    subscription_count = fields.Integer(string='Active Subscriptions', compute='_compute_service_stats', store=True)

    # Support Level - moved from ServiceType to Client
    support_level = fields.Selection([
        ('basic', 'Basic Support'),
        ('standard', 'Standard Support'),
        ('premium', 'Premium Support'),
        ('enterprise', 'Enterprise Support')
    ], string='Support Level', default='standard',
        help='Support level determines SLA requirements and affects service costs')

    # SLA computed from support level
    sla_response_time = fields.Float(string='SLA Response Time (hours)',
                                     compute='_compute_sla_times', store=True,
                                     help='Maximum response time based on support level')
    sla_resolution_time = fields.Float(string='SLA Resolution Time (hours)',
                                       compute='_compute_sla_times', store=True,
                                       help='Maximum resolution time based on support level')

    # Support level impact on workload
    workload_multiplier = fields.Float(string='Workload Multiplier',
                                       compute='_compute_workload_multiplier', store=True,
                                       help='Multiplier for workload factor based on support level')

    # Cost driver quantities
    workstation_count = fields.Integer(string='Workstations', default=0)
    user_count = fields.Integer(string='User Count', default=0)
    server_count = fields.Integer(string='Servers', default=0)
    phone_count = fields.Integer(string='IP Phones', default=0)
    printer_count = fields.Integer(string='Printers', default=0)

    # Relations
    client_service_ids = fields.One2many('client.service', 'client_id', string='Services')
    subscription_ids = fields.One2many('client.service.subscription', 'client_id', string='Subscriptions')
    cost_allocation_ids = fields.One2many('client.cost.allocation', 'client_id', string='Cost Allocations')
    cost_driver_ids = fields.One2many('client.cost.driver', 'client_id', string='Cost Driver Values')

    # Last cost data - ИСПРАВЛЕНО: добавил store=True для полей, которые используются в поиске
    last_monthly_cost = fields.Float(string='Last Monthly Cost', compute='_compute_cost_stats', store=True)
    last_cost_date = fields.Date(string='Last Cost Date', compute='_compute_cost_stats', store=True)
    cost_trend = fields.Selection([
        ('up', 'Increasing'),
        ('down', 'Decreasing'),
        ('stable', 'Stable'),
        ('new', 'New Client')
    ], string='Cost Trend', compute='_compute_cost_trend', store=True)

    @api.depends('support_level')
    def _compute_sla_times(self):
        """Calculate SLA times based on support level"""
        sla_mapping = {
            'basic': {'response': 48.0, 'resolution': 120.0},  # 2 days / 5 days
            'standard': {'response': 24.0, 'resolution': 72.0},  # 1 day / 3 days
            'premium': {'response': 8.0, 'resolution': 24.0},  # 8 hours / 1 day
            'enterprise': {'response': 2.0, 'resolution': 8.0},  # 2 hours / 8 hours
        }

        for partner in self:
            level = partner.support_level or 'standard'
            sla = sla_mapping.get(level, sla_mapping['standard'])
            partner.sla_response_time = sla['response']
            partner.sla_resolution_time = sla['resolution']

    @api.depends('support_level')
    def _compute_workload_multiplier(self):
        """Calculate workload multiplier based on support level"""
        multiplier_mapping = {
            'basic': 0.8,  # Меньше внимания
            'standard': 1.0,  # Базовый уровень
            'premium': 1.3,  # Больше внимания
            'enterprise': 1.6,  # Максимальное внимание
        }

        for partner in self:
            level = partner.support_level or 'standard'
            partner.workload_multiplier = multiplier_mapping.get(level, 1.0)

    def get_effective_workload_factor(self, base_workload_factor):
        """Get effective workload factor including support level multiplier"""
        self.ensure_one()
        return base_workload_factor * self.workload_multiplier

    def get_sla_for_service_type(self, service_type):
        """Get actual SLA for specific service type considering support level"""
        self.ensure_one()
        if not service_type:
            return {
                'response_time': self.sla_response_time,
                'resolution_time': self.sla_resolution_time
            }

        # Берем минимум между клиентским SLA и базовым SLA сервиса
        # (более строгое требование)
        return {
            'response_time': min(self.sla_response_time, service_type.response_time),
            'resolution_time': min(self.sla_resolution_time, service_type.resolution_time)
        }

    # ИСПРАВЛЕНО: поле client.service называется 'status', а не 'active'
    @api.depends('client_service_ids.status', 'subscription_ids.state')
    def _compute_service_stats(self):
        for partner in self:
            # ИСПРАВЛЕНО: используем status='active' вместо поля 'active'
            partner.service_count = len(partner.client_service_ids.filtered(lambda s: s.status == 'active'))
            partner.subscription_count = len(partner.subscription_ids.filtered(lambda s: s.state == 'active'))

    @api.depends('cost_allocation_ids.total_cost', 'cost_allocation_ids.period_date')
    def _compute_cost_stats(self):
        for partner in self:
            latest_allocation = partner.cost_allocation_ids.sorted('period_date', reverse=True)[:1]

            if latest_allocation:
                partner.last_monthly_cost = latest_allocation.total_cost
                partner.last_cost_date = latest_allocation.period_date
            else:
                partner.last_monthly_cost = 0
                partner.last_cost_date = False

    @api.depends('cost_allocation_ids.total_cost', 'cost_allocation_ids.period_date')
    def _compute_cost_trend(self):
        for partner in self:
            allocations = partner.cost_allocation_ids.sorted('period_date', reverse=True)

            if len(allocations) < 2:
                partner.cost_trend = 'new'
            else:
                current = allocations[0].total_cost
                previous = allocations[1].total_cost

                if abs(current - previous) / max(previous, 1) < 0.05:  # 5% threshold
                    partner.cost_trend = 'stable'
                elif current > previous:
                    partner.cost_trend = 'up'
                else:
                    partner.cost_trend = 'down'

    def action_view_services(self):
        """Open client services"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Services - {self.name}',
            'res_model': 'client.service',
            'view_mode': 'tree,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id}
        }

    def action_view_subscriptions(self):
        """Open client subscriptions"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Subscriptions - {self.name}',
            'res_model': 'client.service.subscription',
            'view_mode': 'tree,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id}
        }

    def action_view_cost_allocations(self):
        """Open cost allocations"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cost Allocations - {self.name}',
            'res_model': 'client.cost.allocation',
            'view_mode': 'tree,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id}
        }

    def action_create_subscription(self):
        """Create new subscription for client"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'New Subscription - {self.name}',
            'res_model': 'client.service.subscription',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_client_id': self.id,
                'default_name': f'Subscription - {self.name}',
            }
        }

    def update_cost_drivers(self):
        """Update cost driver quantities from services"""
        for partner in self:
            # Автоматически обновляем драйверы на основе услуг клиента

            # Получаем все драйверы для этого клиента
            service_counts = {}

            for service in partner.client_service_ids.filtered(lambda s: s.status == 'active'):
                service_type = service.service_type_id.service_type
                if service_type not in service_counts:
                    service_counts[service_type] = 0
                service_counts[service_type] += service.quantity

            # Обновляем поля
            partner.workstation_count = service_counts.get('workstation', 0)
            partner.server_count = service_counts.get('server', 0)
            partner.printer_count = service_counts.get('printer', 0)
            # Можно добавить другие типы по мере необходимости