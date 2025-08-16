from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class ClientServiceSubscription(models.Model):
    _name = 'client.service.subscription'
    _description = 'Client Service Subscription'
    _order = 'client_id, start_date desc'

    name = fields.Char(string='Subscription Name', required=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)])

    # Subscription details
    template_id = fields.Many2one('sale.subscription.template', string='Subscription Template')
    subscription_id = fields.Many2one('sale.subscription', string='Odoo Subscription')

    # Period
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date(string='End Date')
    recurring_interval = fields.Integer(string='Recurring Interval', default=1)
    recurring_rule_type = fields.Selection([
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('yearly', 'Year(s)')
    ], string='Recurring Rule Type', default='monthly', required=True)

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
    ], string='Status', default='draft', required=True)

    # Services
    service_line_ids = fields.One2many('client.service.subscription.line', 'subscription_id',
                                       string='Service Lines')

    # Invoicing
    auto_invoice = fields.Boolean(string='Auto Invoice', default=True)
    invoice_day = fields.Integer(string='Invoice Day', default=1, help='Day of month to generate invoice')
    next_invoice_date = fields.Date(string='Next Invoice Date', compute='_compute_next_invoice_date', store=True)

    active = fields.Boolean(default=True)

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

    def action_activate(self):
        """Activate subscription and create Odoo subscription"""
        for record in self:
            if not record.subscription_id:
                # Create subscription template if needed
                if not record.template_id:
                    template_vals = {
                        'name': f'IT Services - {record.client_id.name}',
                        'recurring_rule_type': record.recurring_rule_type,
                        'recurring_interval': record.recurring_interval,
                    }
                    record.template_id = self.env['sale.subscription.template'].create(template_vals)

                # Create subscription
                subscription_vals = {
                    'name': record.name,
                    'partner_id': record.client_id.id,
                    'template_id': record.template_id.id,
                    'date_start': record.start_date,
                    'recurring_rule_type': record.recurring_rule_type,
                    'recurring_interval': record.recurring_interval,
                }
                subscription = self.env['sale.subscription'].create(subscription_vals)
                record.subscription_id = subscription.id

                # Create subscription lines
                for line in record.service_line_ids:
                    line._create_subscription_line()

            record.state = 'active'

    def action_generate_invoice(self):
        """Generate invoice for this period"""
        for record in self:
            if record.subscription_id and record.auto_invoice:
                record.subscription_id.recurring_invoice()

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
                subscription._compute_next_invoice_date()
            except Exception as e:
                # Log error but continue with other subscriptions
                _logger.error(f"Failed to generate invoice for subscription {subscription.name}: {e}")


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
    subscription_line_id = fields.Many2one('sale.subscription.line', string='Odoo Subscription Line')

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.quantity * record.unit_price

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.unit_price = self.service_id.sales_price
            self.name = self.service_id.name

    def _create_subscription_line(self):
        """Create corresponding line in Odoo subscription"""
        if self.subscription_id.subscription_id:
            # Create product if not exists
            product = self._get_or_create_product()

            line_vals = {
                'subscription_id': self.subscription_id.subscription_id.id,
                'product_id': product.id,
                'name': self.name or self.service_id.name,
                'quantity': self.quantity,
                'price_unit': self.unit_price,
            }

            subscription_line = self.env['sale.subscription.line'].create(line_vals)
            self.subscription_line_id = subscription_line.id

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
                'recurring_invoice': True,
                'list_price': self.service_id.sales_price,
                'categ_id': self.env.ref('product.product_category_all').id,
            }
            product = Product.create(product_vals)

        return product