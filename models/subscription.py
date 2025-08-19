from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class ClientServiceSubscription(models.Model):
    _name = 'client.service.subscription'
    _description = 'Client Service Subscription'
    _order = 'client_id, start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Subscription Name', required=True, tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)], tracking=True)

    # Remove dependency on external subscription module
    # template_id = fields.Many2one('sale.subscription.template', string='Subscription Template')
    # subscription_id = fields.Many2one('sale.subscription', string='Odoo Subscription')

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
    currency_id = fields.Many2one('res.currency', string='Currency',
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
    next_invoice_date = fields.Date(string='Next Invoice Date', store=True)

    # Integration fields (optional)
    external_subscription_id = fields.Char(string='External Subscription ID',
                                           help='ID from external subscription system')

    active = fields.Boolean(default=True)

    @api.onchange('start_date', 'recurring_interval', 'recurring_rule_type', 'invoice_day')
    def _onchange_compute_next_invoice_date(self):
        """Calculate initial next invoice date when subscription details change"""
        for record in self:
            if record.start_date:
                if record.recurring_rule_type == 'monthly':
                    next_date = record.start_date.replace(day=record.invoice_day or 1)
                    if next_date <= record.start_date:
                        next_date = next_date + relativedelta(months=1)
                    record.next_invoice_date = next_date
                else:
                    record.next_invoice_date = record.start_date
            else:
                record.next_invoice_date = False

    def _update_next_invoice_date(self):
        """Update next invoice date after invoice creation"""
        for record in self:
            if record.next_invoice_date and record.recurring_rule_type == 'monthly':
                if record.recurring_interval:
                    next_date = record.next_invoice_date + relativedelta(months=record.recurring_interval)
                else:
                    next_date = record.next_invoice_date + relativedelta(months=1)
                try:
                    next_date = next_date.replace(day=record.invoice_day or 1)
                except ValueError:
                    next_date = next_date.replace(day=min(record.invoice_day or 1, 28))
                record.next_invoice_date = next_date
            elif record.recurring_rule_type == 'yearly':
                if record.next_invoice_date:
                    next_date = record.next_invoice_date + relativedelta(years=record.recurring_interval or 1)
                    record.next_invoice_date = next_date

    @api.depends('service_line_ids.total_price')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.service_line_ids.mapped('total_price'))

    @api.depends('start_date', 'recurring_interval', 'recurring_rule_type', 'invoice_day')
    def _compute_next_invoice_date(self):
        for record in self:
            if record.start_date:
                if record.recurring_rule_type == 'monthly':
                    # Next month, specific day
                    next_date = record.start_date.replace(day=record.invoice_day)
                    if next_date <= record.start_date:
                        next_date = next_date + relativedelta(months=1)
                    record.next_invoice_date = next_date
                else:
                    record.next_invoice_date = record.start_date
            else:
                record.next_invoice_date = False

    @api.model
    def _subscription_module_installed(self):
        """Check if external subscription module is available"""
        return 'sale.subscription' in self.env.registry._init_modules

    def action_activate(self):
        """Activate subscription"""
        for record in self:
            # Try to integrate with external subscription module if available
            if self._subscription_module_installed():
                record._try_create_external_subscription()

            record.state = 'active'
            record.message_post(body="Subscription activated")

    def _try_create_external_subscription(self):
        """Try to create external subscription if module is available"""
        try:
            if 'sale.subscription' in self.env:
                # Create subscription if external module is available
                subscription_vals = {
                    'name': self.name,
                    'partner_id': self.client_id.id,
                    'date_start': self.start_date,
                    'recurring_rule_type': self.recurring_rule_type,
                    'recurring_interval': self.recurring_interval,
                }
                subscription = self.env['sale.subscription'].create(subscription_vals)
                self.external_subscription_id = str(subscription.id)

                # Create subscription lines
                for line in self.service_line_ids:
                    line._try_create_external_subscription_line(subscription.id)
        except Exception as e:
            # Log error but don't fail activation
            self.message_post(body=f"Could not create external subscription: {e}")

    def action_generate_invoice(self):
        """Generate invoice for this period"""
        for record in self:
            # Try external subscription first
            if record.external_subscription_id and self._subscription_module_installed():
                try:
                    external_sub = self.env['sale.subscription'].browse(int(record.external_subscription_id))
                    if external_sub.exists():
                        external_sub.recurring_invoice()
                        record.message_post(body="Invoice generated via external subscription")
                        return
                except Exception:
                    pass

            # Fallback to manual invoice creation
            record._create_manual_invoice()

    def _create_manual_invoice(self):
        """Create invoice manually without external subscription module"""
        self.ensure_one()

        # Create invoice
        invoice_vals = {
            'partner_id': self.client_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'ref': f"{self.name} - {self.next_invoice_date.strftime('%m/%Y') if self.next_invoice_date else ''}",
            'narration': f"Service subscription: {self.name}",
        }

        invoice = self.env['account.move'].create(invoice_vals)

        # Add invoice lines
        for line in self.service_line_ids:
            product = line._get_or_create_product()

            invoice_line_vals = {
                'move_id': invoice.id,
                'product_id': product.id,
                'name': line.name or line.service_id.name,
                'quantity': line.quantity,
                'price_unit': line.unit_price,
                'account_id': self._get_income_account().id,
            }
            self.env['account.move.line'].create(invoice_line_vals)

        self.message_post(body=f"Manual invoice created: {invoice.name}")
        return invoice

    def _get_income_account(self):
        """Get default income account"""
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not income_account:
            income_account = self.env['account.account'].search([
                ('code', 'like', '7%'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        return income_account

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
            self.unit_price = self.service_id.sales_price
            self.name = self.service_id.name

    def _try_create_external_subscription_line(self, external_subscription_id):
        """Try to create line in external subscription system"""
        try:
            if 'sale.subscription.line' in self.env:
                product = self._get_or_create_product()

                line_vals = {
                    'subscription_id': external_subscription_id,
                    'product_id': product.id,
                    'name': self.name or self.service_id.name,
                    'quantity': self.quantity,
                    'price_unit': self.unit_price,
                }

                subscription_line = self.env['sale.subscription.line'].create(line_vals)
                self.external_line_id = str(subscription_line.id)
        except Exception as e:
            # Log error but don't fail
            self.subscription_id.message_post(body=f"Could not create external subscription line: {e}")

    def _get_or_create_product(self):
        """Get or create product for this service"""
        Product = self.env['product.product']

        # Try to find existing product
        product = Product.search([
            ('default_code', '=', self.service_id.code),
            ('name', '=', self.service_id.name)
        ], limit=1)

        if not product:
            # Create new product
            product_vals = {
                'name': self.service_id.name,
                'default_code': self.service_id.code,
                'type': 'service',
                'list_price': self.service_id.sales_price,
                'categ_id': self._get_service_category().id,
            }
            product = Product.create(product_vals)

        return product

    def _get_service_category(self):
        """Get or create IT Services product category"""
        category = self.env['product.category'].search([
            ('name', '=', 'IT Services')
        ], limit=1)

        if not category:
            category = self.env['product.category'].create({
                'name': 'IT Services',
            })
        return category