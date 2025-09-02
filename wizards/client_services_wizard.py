# wizards/client_services_wizard.py - НОВЫЙ ВИЗАРД

from odoo import models, fields, api
from datetime import datetime, date


class ClientServicesWizard(models.TransientModel):
    _name = 'client.services.wizard'
    _description = 'Client Services Summary Wizard'

    # Параметры визарда
    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)])
    period_date = fields.Date(string='Period', required=True, default=fields.Date.today)
    include_inactive = fields.Boolean(string='Include Inactive Services', default=False)

    # Фильтры
    pool_ids = fields.Many2many('cost.pool', string='Filter by Cost Pools',
                                help='Leave empty to include all pools')
    service_category_ids = fields.Many2many('cost.driver.category', string='Filter by Categories',
                                            help='Leave empty to include all categories')

    # Результаты
    service_line_ids = fields.One2many('client.services.wizard.line', 'wizard_id',
                                       string='Client Services')

    # Итоги
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_totals')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_totals')
    total_revenue = fields.Monetary(string='Total Revenue', compute='_compute_totals')
    total_profit = fields.Monetary(string='Total Profit', compute='_compute_totals')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('service_line_ids.quantity', 'service_line_ids.total_cost',
                 'service_line_ids.total_revenue')
    def _compute_totals(self):
        for wizard in self:
            lines = wizard.service_line_ids
            wizard.total_quantity = sum(lines.mapped('quantity'))
            wizard.total_cost = sum(lines.mapped('total_cost'))
            wizard.total_revenue = sum(lines.mapped('total_revenue'))
            wizard.total_profit = wizard.total_revenue - wizard.total_cost

    def action_load_services(self):
        """Загрузить услуги клиента"""
        self.ensure_one()

        # Удалить старые строки
        self.service_line_ids.unlink()

        # Поиск всех драйверов затрат для клиента
        domain = [('client_id', '=', self.client_id.id)]

        # Применить фильтры
        if self.pool_ids:
            domain.append(('driver_id.pool_id', 'in', self.pool_ids.ids))
        if self.service_category_ids:
            domain.append(('driver_id.driver_category_id', 'in', self.service_category_ids.ids))
        if not self.include_inactive:
            domain.append(('driver_id.active', '=', True))

        client_drivers = self.env['client.cost.driver'].search(domain)

        # Создать строки результатов
        for driver_allocation in client_drivers:
            driver = driver_allocation.driver_id

            self.env['client.services.wizard.line'].create({
                'wizard_id': self.id,
                'driver_id': driver.id,
                'driver_name': driver.name,
                'category_name': driver.driver_category_id.name if driver.driver_category_id else 'Uncategorized',
                'pool_name': driver.pool_id.name,
                'unit_name': driver.unit_id.name,
                'quantity': driver_allocation.quantity,
                'unit_cost': driver.cost_per_unit,
                'unit_price': driver.sales_price_per_unit,
                'total_cost': driver_allocation.quantity * driver.cost_per_unit,
                'total_revenue': driver_allocation.quantity * driver.sales_price_per_unit,
                'is_license': driver.is_license_unit if hasattr(driver, 'is_license_unit') else False,
                'license_type': driver.license_type if hasattr(driver, 'license_type') else '',
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'client.services.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_export_to_excel(self):
        """Экспорт в Excel"""
        # Можно добавить позже
        self.ensure_one()
        return self.env.ref('cost_allocation.action_client_services_report').report_action(self)

    def action_create_subscription(self):
        """Создать подписку на основе услуг"""
        self.ensure_one()

        if not self.service_line_ids:
            raise UserError("No services found. Please load services first.")

        # Создать подписку
        subscription = self.env['client.service.subscription'].create({
            'name': f"{self.client_id.name} Services - {self.period_date.strftime('%Y-%m')}",
            'client_id': self.client_id.id,
            'start_date': self.period_date,
            'status': 'draft',
        })

        # Создать строки подписки
        for line in self.service_line_ids:
            # Найти или создать service catalog entry
            service_catalog = self.env['service.catalog'].search([
                ('name', 'ilike', line.driver_name)
            ], limit=1)

            if not service_catalog:
                # Создать новый service catalog
                category = self.env['service.category'].search([
                    ('name', 'ilike', line.category_name)
                ], limit=1)
                if not category:
                    category = self.env['service.category'].create({
                        'name': line.category_name,
                        'service_type': 'support'
                    })

                service_catalog = self.env['service.catalog'].create({
                    'name': line.driver_name,
                    'category_id': category.id,
                    'unit_of_measure': 'unit',
                    'base_cost': line.unit_cost,
                    'markup_percent': (
                                (line.unit_price - line.unit_cost) / line.unit_cost * 100) if line.unit_cost > 0 else 0,
                })

            # Создать subscription line
            self.env['client.service.subscription.line'].create({
                'subscription_id': subscription.id,
                'service_catalog_id': service_catalog.id,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'total_price': line.total_revenue,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'client.service.subscription',
            'res_id': subscription.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ClientServicesWizardLine(models.TransientModel):
    _name = 'client.services.wizard.line'
    _description = 'Client Services Wizard Line'

    wizard_id = fields.Many2one('client.services.wizard', required=True, ondelete='cascade')

    # Service information
    driver_id = fields.Many2one('cost.driver', string='Driver')
    driver_name = fields.Char(string='Service Name')
    category_name = fields.Char(string='Category')
    pool_name = fields.Char(string='Cost Pool')
    unit_name = fields.Char(string='Unit')

    # Quantities and pricing
    quantity = fields.Float(string='Quantity')
    unit_cost = fields.Monetary(string='Unit Cost', currency_field='currency_id')
    unit_price = fields.Monetary(string='Unit Price', currency_field='currency_id')
    total_cost = fields.Monetary(string='Total Cost', currency_field='currency_id')
    total_revenue = fields.Monetary(string='Total Revenue', currency_field='currency_id')
    profit = fields.Monetary(string='Profit', compute='_compute_profit', currency_field='currency_id')

    # License info
    is_license = fields.Boolean(string='Is License')
    license_type = fields.Char(string='License Type')

    currency_id = fields.Many2one('res.currency', related='wizard_id.currency_id')

    @api.depends('total_revenue', 'total_cost')
    def _compute_profit(self):
        for line in self:
            line.profit = line.total_revenue - line.total_cost