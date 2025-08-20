from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class ClientServiceSubscription(models.Model):
    _name = 'client.service.subscription'
    _description = 'Client Service Subscription'
    _order = 'client_id, start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'sequence.helper']  # ДОБАВЛЕНО: sequence.helper

    # ДОБАВЛЕНО: поле кода для подписок
    code = fields.Char(string='Subscription Code', readonly=True, copy=False)
    name = fields.Char(string='Subscription Name', required=True, tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)], tracking=True)

    # Period
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today, tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    recurring_interval = fields.Integer(string='Recurring Interval', default=1)
    recurring_rule_type = fields.Selection([
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('yearly', 'Year(s)')
    ], string='Recurring Rule Type', default='monthly', required=True, tracking=True)

    # Pricing
    total_amount = fields.Float(string='Monthly Amount', compute='_compute_total_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', required=True, tracking=True)

    # Services
    service_line_ids = fields.One2many('client.service.subscription.line', 'subscription_id',
                                       string='Service Lines')

    # Invoicing
    auto_invoice = fields.Boolean(string='Auto Invoice', default=True)
    invoice_day = fields.Integer(string='Invoice Day', default=1, help='Day of month to generate invoice')
    next_invoice_date = fields.Date(string='Next Invoice Date', compute='_compute_next_invoice_date', store=True)

    # Analytics
    total_invoiced = fields.Float(string='Total Invoiced', compute='_compute_invoice_stats')
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_stats')

    # ИСПРАВЛЕНО: добавлено поле company_id
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends('service_line_ids.total_price')
    def _compute_total_amount(self):
        for subscription in self:
            subscription.total_amount = sum(subscription.service_line_ids.mapped('total_price'))

    @api.depends('start_date', 'recurring_interval', 'recurring_rule_type', 'state')
    def _compute_next_invoice_date(self):
        for subscription in self:
            if subscription.state != 'active' or not subscription.auto_invoice:
                subscription.next_invoice_date = False
                continue

            if not subscription.start_date:
                subscription.next_invoice_date = False
                continue

            # Calculate next invoice date based on recurring rule
            if subscription.recurring_rule_type == 'monthly':
                # Find the next invoice date
                today = fields.Date.today()
                start = subscription.start_date

                # If subscription just started, next invoice is on invoice_day of next month
                if start >= today:
                    next_month = start + relativedelta(months=1)
                    subscription.next_invoice_date = next_month.replace(day=subscription.invoice_day)
                else:
                    # Find next occurrence based on recurring interval
                    months_passed = ((today.year - start.year) * 12 + today.month - start.month)
                    next_period = months_passed + subscription.recurring_interval
                    next_date = start + relativedelta(months=next_period)
                    subscription.next_invoice_date = next_date.replace(day=subscription.invoice_day)
            else:
                # For other intervals, use simpler logic
                subscription.next_invoice_date = subscription.start_date + relativedelta(
                    days=subscription.recurring_interval if subscription.recurring_rule_type == 'daily' else 0,
                    weeks=subscription.recurring_interval if subscription.recurring_rule_type == 'weekly' else 0,
                    months=subscription.recurring_interval if subscription.recurring_rule_type == 'monthly' else 0,
                    years=subscription.recurring_interval if subscription.recurring_rule_type == 'yearly' else 0
                )

    def _compute_invoice_stats(self):
        for subscription in self:
            invoices = self.env['account.move'].search([
                ('subscription_id', '=', subscription.id),
                ('move_type', '=', 'out_invoice')
            ])
            subscription.invoice_count = len(invoices)
            subscription.total_invoiced = sum(invoices.mapped('amount_total'))

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Invoices - {self.name}',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id}
        }

    def action_generate_invoice(self):
        """Manually generate invoice for this subscription"""
        self.ensure_one()
        if not self.service_line_ids:
            from odoo.exceptions import UserError
            raise UserError("Cannot generate invoice without service lines.")

        invoice_vals = self._prepare_invoice_vals()
        invoice = self.env['account.move'].create(invoice_vals)

        # Create invoice lines
        for line in self.service_line_ids:
            line_vals = line._prepare_invoice_line_vals(invoice)
            self.env['account.move.line'].create(line_vals)

        # ИСПРАВЛЕНО: в Odoo 17 достаточно invalidate cache, итоги пересчитываются автоматически
        invoice.invalidate_recordset(['amount_total', 'amount_untaxed', 'amount_tax'])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Generated Invoice',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'views': [(False, 'form')]
        }

    def _prepare_invoice_vals(self):
        """Prepare invoice values"""
        return {
            'partner_id': self.client_id.id,
            'move_type': 'out_invoice',
            'subscription_id': self.id,
            'currency_id': self.currency_id.id,
            'invoice_date': fields.Date.today(),
            'ref': f'Subscription: {self.name}'
        }

    def _update_next_invoice_date(self):
        """Update next invoice date after generating invoice"""
        for subscription in self:
            if subscription.recurring_rule_type == 'monthly':
                subscription.next_invoice_date += relativedelta(months=subscription.recurring_interval)
            elif subscription.recurring_rule_type == 'yearly':
                subscription.next_invoice_date += relativedelta(years=subscription.recurring_interval)
            elif subscription.recurring_rule_type == 'weekly':
                subscription.next_invoice_date += timedelta(weeks=subscription.recurring_interval)
            elif subscription.recurring_rule_type == 'daily':
                subscription.next_invoice_date += timedelta(days=subscription.recurring_interval)

    def _get_default_income_account(self):
        """Get default income account for invoicing"""
        # ИСПРАВЛЕНО: более надежный поиск аккаунта дохода
        # Сначала ищем по коду 7xxx (доходы)
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False)
        ], limit=1)

        # Если не найден income account, ищем по коду 70% (выручка)
        if not income_account:
            income_account = self.env['account.account'].search([
                ('code', '=like', '70%'),
                ('company_id', '=', self.env.company.id),
                ('deprecated', '=', False)
            ], limit=1)

        # Крайний случай - любой доходный счет
        if not income_account:
            income_account = self.env['account.account'].search([
                ('code', '=like', '7%'),
                ('company_id', '=', self.env.company.id),
                ('deprecated', '=', False)
            ], limit=1)

        return income_account

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ДОБАВЛЕНО: автогенерация кода подписки
            if not vals.get('code'):
                vals['code'] = self._generate_code('client.service.subscription.code')
        return super().create(vals_list)

    @api.model
    def cron_generate_invoices(self):
        """Cron job to generate invoices"""
        today = fields.Date.today()
        subscriptions = self.search([
            ('state', '=', 'active'),
            ('auto_invoice', '=', True),
            ('next_invoice_date', '<=', today)
        ])

        for subscription in subscriptions:
            try:
                subscription.action_generate_invoice()
                # Update next invoice date
                subscription._update_next_invoice_date()
            except Exception as e:
                # Log error but continue with other subscriptions
                subscription.message_post(body=f"Failed to generate invoice: {e}")


class ClientServiceSubscriptionLine(models.Model):
    _name = 'client.service.subscription.line'
    _description = 'Client Service Subscription Line'
    _order = 'subscription_id, sequence, service_id'

    subscription_id = fields.Many2one('client.service.subscription', string='Subscription',
                                      required=True, ondelete='cascade')
    client_id = fields.Many2one(related='subscription_id.client_id', store=True)
    # ИСПРАВЛЕНО: добавлен related currency_id от subscription
    currency_id = fields.Many2one(related='subscription_id.currency_id', store=True)

    sequence = fields.Integer(string='Sequence', default=10)
    service_id = fields.Many2one('service.catalog', string='Service', required=True)

    # Service details
    name = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    unit_price = fields.Float(string='Unit Price', required=True)
    total_price = fields.Float(string='Total Price', compute='_compute_total_price', store=True)

    # Links
    client_service_ids = fields.Many2many('client.service', string='Client Services',
                                          help='Physical services/equipment linked to this subscription line')

    # External integration (optional)
    external_line_id = fields.Char(string='External Line ID', help='ID from external subscription system')

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.quantity * record.unit_price

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            # Set default description and price from service catalog
            self.name = self.service_id.description or self.service_id.name
            # ИСПРАВЛЕНО: используем sales_price из service.catalog
            self.unit_price = self.service_id.sales_price

    def _prepare_invoice_line_vals(self, invoice):
        """Prepare invoice line values"""
        # ИСПРАВЛЕНО: добавлена проверка на наличие account
        account = self.service_id.property_account_income_id or self.subscription_id._get_default_income_account()
        if not account:
            from odoo.exceptions import UserError
            raise UserError(f"No income account found for service '{self.service_id.name}'. "
                            f"Please configure an income account for this service.")

        return {
            'move_id': invoice.id,
            'name': self.name or self.service_id.name,
            'quantity': self.quantity,
            'price_unit': self.unit_price,
            'account_id': account.id,
            'subscription_line_id': self.id
        }