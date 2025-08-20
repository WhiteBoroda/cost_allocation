from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Service statistics
    service_count = fields.Integer(string='Active Services', compute='_compute_service_stats')
    subscription_count = fields.Integer(string='Active Subscriptions', compute='_compute_service_stats')

    # Cost driver quantities
    workstation_count = fields.Integer(string='Workstations', default=0)
    user_count = fields.Integer(string='Users', default=0)
    server_count = fields.Integer(string='Servers', default=0)
    phone_count = fields.Integer(string='IP Phones', default=0)
    printer_count = fields.Integer(string='Printers', default=0)

    # Relations
    client_service_ids = fields.One2many('client.service', 'client_id', string='Services')
    subscription_ids = fields.One2many('client.service.subscription', 'client_id', string='Subscriptions')
    cost_allocation_ids = fields.One2many('client.cost.allocation', 'client_id', string='Cost Allocations')
    cost_driver_ids = fields.One2many('client.cost.driver', 'client_id', string='Cost Driver Values')

    # Last cost data
    last_monthly_cost = fields.Float(string='Last Monthly Cost', compute='_compute_cost_stats')
    last_cost_date = fields.Date(string='Last Cost Date', compute='_compute_cost_stats')
    cost_trend = fields.Selection([
        ('up', 'Increasing'),
        ('down', 'Decreasing'),
        ('stable', 'Stable'),
        ('new', 'New Client')
    ], string='Cost Trend', compute='_compute_cost_trend')

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

            # Получаем все драйверы
            drivers = self.env['cost.driver'].search([])

            for driver in drivers:
                # Определяем количество на основе названия драйвера
                quantity = 0

                if 'workstation' in driver.name.lower() or 'компьютер' in driver.name.lower():
                    # Считаем рабочие станции
                    workstations = partner.client_service_ids.filtered(
                        lambda s: any(word in s.service_type_id.name.lower()
                                      for word in ['workstation', 'desktop', 'laptop', 'компьютер', 'ноутбук'])
                    )
                    quantity = sum(workstations.mapped('quantity'))
                    partner.workstation_count = quantity

                elif 'user' in driver.name.lower() or 'пользователь' in driver.name.lower():
                    # Считаем пользователей
                    user_services = partner.client_service_ids.filtered(
                        lambda s: 'user' in s.service_type_id.name.lower() or 'пользователь' in s.service_type_id.name.lower()
                    )
                    quantity = sum(user_services.mapped('quantity'))
                    partner.user_count = quantity

                elif 'server' in driver.name.lower() or 'сервер' in driver.name.lower():
                    # Считаем серверы
                    servers = partner.client_service_ids.filtered(
                        lambda s: 'server' in s.service_type_id.name.lower() or 'сервер' in s.service_type_id.name.lower()
                    )
                    quantity = sum(servers.mapped('quantity'))
                    partner.server_count = quantity

                elif 'phone' in driver.name.lower() or 'телефон' in driver.name.lower():
                    # Считаем телефоны
                    phones = partner.client_service_ids.filtered(
                        lambda s: any(word in s.service_type_id.name.lower()
                                      for word in ['phone', 'ip', 'телефон'])
                    )
                    quantity = sum(phones.mapped('quantity'))
                    partner.phone_count = quantity

                elif 'printer' in driver.name.lower() or 'принтер' in driver.name.lower():
                    # Считаем принтеры
                    printers = partner.client_service_ids.filtered(
                        lambda s: any(word in s.service_type_id.name.lower()
                                      for word in ['printer', 'mfp', 'принтер'])
                    )
                    quantity = sum(printers.mapped('quantity'))
                    partner.printer_count = quantity

                # Обновляем или создаем запись драйвера для клиента
                if quantity > 0:
                    client_driver = self.env['client.cost.driver'].search([
                        ('driver_id', '=', driver.id),
                        ('client_id', '=', partner.id)
                    ])

                    if client_driver:
                        client_driver.quantity = quantity
                    else:
                        self.env['client.cost.driver'].create({
                            'driver_id': driver.id,
                            'client_id': partner.id,
                            'quantity': quantity
                        })

    @api.model
    def cron_update_all_cost_drivers(self):
        """Cron job to update cost drivers for all clients"""
        clients = self.search([('is_company', '=', True)])
        clients.update_cost_drivers()