from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class BillingAutomation(models.Model):
    _name = 'billing.automation'
    _description = 'Automated Billing for IT Services'
    _order = 'next_run_date'

    name = fields.Char(string='Automation Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Schedule
    billing_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], string='Billing Period', default='monthly', required=True)

    billing_day = fields.Integer(string='Billing Day of Month', default=1,
                                 help='Day of month to generate invoices (1-28)')

    next_run_date = fields.Date(string='Next Run Date', required=True, default=fields.Date.today)
    last_run_date = fields.Date(string='Last Run Date')

    # Scope
    client_ids = fields.Many2many('res.partner', string='Clients',
                                  domain=[('is_company', '=', True)],
                                  help='Leave empty to include all clients')

    subscription_ids = fields.Many2many('client.service.subscription', string='Subscriptions',
                                        help='Leave empty to include all active subscriptions')

    # Templates
    invoice_template_id = fields.Many2one('account.move', string='Invoice Template',
                                          domain=[('move_type', '=', 'out_invoice'), ('state', '=', 'draft')])

    # Journal and accounts
    journal_id = fields.Many2one('account.journal', string='Sales Journal',
                                 domain=[('type', '=', 'sale')], required=True)

    # Automation settings
    auto_confirm_invoices = fields.Boolean(string='Auto Confirm Invoices', default=True)
    auto_send_invoices = fields.Boolean(string='Auto Send Invoices', default=False)
    auto_create_acts = fields.Boolean(string='Auto Create Work Acts', default=True)

    # Accounting integration
    include_cost_allocation = fields.Boolean(string='Include Cost Allocation Data', default=True)
    cost_calculation_delay = fields.Integer(string='Cost Calculation Delay (days)', default=5,
                                            help='Days to wait for cost allocation calculation')

    # Notification
    notify_user_ids = fields.Many2many('res.users', string='Notify Users')

    # Statistics
    last_invoice_count = fields.Integer(string='Last Invoice Count', readonly=True)
    total_invoices_created = fields.Integer(string='Total Invoices Created', readonly=True)

    def action_run_billing(self):
        """Manual run of billing automation"""
        self.ensure_one()
        return self._run_billing()

    def _run_billing(self):
        """Execute billing automation"""
        if not self.active:
            return

        # Calculate period dates
        period_start, period_end = self._get_billing_period()

        # Get subscriptions to bill
        subscriptions = self._get_subscriptions_to_bill()

        invoices_created = []
        acts_created = []

        for subscription in subscriptions:
            try:
                # Create invoice
                invoice = self._create_invoice(subscription, period_start, period_end)
                if invoice:
                    invoices_created.append(invoice)

                    # Create work act if needed
                    if self.auto_create_acts:
                        act = self._create_work_act(subscription, invoice, period_start, period_end)
                        if act:
                            acts_created.append(act)

                    # Update subscription next invoice date
                    subscription._update_next_invoice_date()

            except Exception as e:
                # Log error and continue
                self.env['ir.logging'].create({
                    'name': f'Billing Automation Error: {subscription.name}',
                    'type': 'server',
                    'level': 'ERROR',
                    'message': str(e),
                    'func': '_run_billing',
                    'path': __file__,
                    'line': 0,
                })

        # Update automation record
        self.last_run_date = fields.Date.today()
        self.last_invoice_count = len(invoices_created)
        self.total_invoices_created += len(invoices_created)
        self._calculate_next_run_date()

        # Send notifications
        if self.notify_user_ids and invoices_created:
            self._send_notifications(invoices_created, acts_created)

        return {
            'invoices': invoices_created,
            'acts': acts_created
        }

    def _get_billing_period(self):
        """Calculate billing period start and end dates"""
        today = fields.Date.today()

        if self.billing_period == 'monthly':
            start = today.replace(day=1)
            end = (start + relativedelta(months=1)) - timedelta(days=1)
        elif self.billing_period == 'quarterly':
            quarter = (today.month - 1) // 3 + 1
            start = today.replace(month=(quarter - 1) * 3 + 1, day=1)
            end = (start + relativedelta(months=3)) - timedelta(days=1)
        else:  # yearly
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)

        return start, end

    def _get_subscriptions_to_bill(self):
        """Get subscriptions that need billing"""
        domain = [('state', '=', 'active')]

        if self.subscription_ids:
            domain.append(('id', 'in', self.subscription_ids.ids))
        elif self.client_ids:
            domain.append(('client_id', 'in', self.client_ids.ids))

        # Check next invoice date
        domain.append(('next_invoice_date', '<=', fields.Date.today()))

        return self.env['client.service.subscription'].search(domain)

    def _create_invoice(self, subscription, period_start, period_end):
        """Create invoice for subscription"""
        # Check if invoice already exists for this period
        existing_invoice = self.env['account.move'].search([
            ('partner_id', '=', subscription.client_id.id),
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', period_start),
            ('invoice_date', '<=', period_end),
            ('ref', 'ilike', subscription.name)
        ], limit=1)

        if existing_invoice:
            return existing_invoice

        # Get cost allocation data if needed
        cost_allocation = None
        if self.include_cost_allocation:
            cost_allocation = self.env['client.cost.allocation'].search([
                ('client_id', '=', subscription.client_id.id),
                ('period_date', '>=', period_start),
                ('period_date', '<=', period_end),
                ('state', '=', 'confirmed')
            ], limit=1)

        # Create invoice
        invoice_vals = {
            'partner_id': subscription.client_id.id,
            'move_type': 'out_invoice',
            'journal_id': self.journal_id.id,
            'invoice_date': fields.Date.today(),
            'ref': f"{subscription.name} - {period_start.strftime('%m/%Y')}",
            'narration': f"IT Services for period {period_start} - {period_end}",
        }

        invoice = self.env['account.move'].create(invoice_vals)

        # Add invoice lines from subscription
        for line in subscription.service_line_ids:
            # Get or create product for service type
            product = self._get_or_create_product(line.service_id)

            invoice_line_vals = {
                'move_id': invoice.id,
                'product_id': product.id,
                'name': line.name or line.service_id.name,
                'quantity': line.quantity,
                'price_unit': line.unit_price,
                'account_id': self._get_income_account().id,
            }
            self.env['account.move.line'].create(invoice_line_vals)

        # Add cost allocation summary if available
        if cost_allocation:
            self._add_cost_allocation_line(invoice, cost_allocation)

        # Auto confirm if needed
        if self.auto_confirm_invoices:
            invoice.action_post()

        # Auto send if needed
        if self.auto_send_invoices and invoice.state == 'posted':
            invoice.action_send_and_print()

        return invoice

    def _create_work_act(self, subscription, invoice, period_start, period_end):
        """Create work completion act"""
        # This would integrate with Ukrainian localization for acts
        # For now, create a simple document or log entry

        # Log the act creation
        self.env['ir.logging'].create({
            'name': f"Work Act Created: {subscription.name}",
            'type': 'server',
            'level': 'INFO',
            'message': f"Work completion act for {subscription.client_id.name} - Period: {period_start} to {period_end}",
            'func': '_create_work_act',
            'path': __file__,
            'line': 0,
        })

        # Return a dummy record for compatibility
        return self.env['ir.logging'].browse([1]) if self.env['ir.logging'].search([], limit=1) else None

    def _add_cost_allocation_line(self, invoice, cost_allocation):
        """Add cost breakdown as invoice line comment"""
        description = f"""
Cost Breakdown:
- Direct Costs: {cost_allocation.direct_cost:.2f}
- Indirect Costs: {cost_allocation.indirect_cost:.2f} 
- Administrative: {cost_allocation.admin_cost:.2f}
- Total Cost: {cost_allocation.total_cost:.2f}
"""

        # Add as note line
        self.env['account.move.line'].create({
            'move_id': invoice.id,
            'name': description,
            'display_type': 'line_note',
        })

    def _get_income_account(self):
        """Get default income account"""
        # Try different approaches for finding income account
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not income_account:
            # Fallback: try by name pattern
            income_account = self.env['account.account'].search([
                ('name', 'ilike', 'income'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        if not income_account:
            # Last fallback: try by code pattern
            income_account = self.env['account.account'].search([
                ('code', 'like', '7%'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        return income_account

    def _get_or_create_product(self, service_catalog):
        """Get or create product for service catalog item"""
        product = self.env['product.template'].search([
            ('default_code', '=', f"SRV_{service_catalog.code}")
        ], limit=1)

        if not product:
            category = self.env['product.category'].search([
                ('name', '=', 'IT Services')
            ], limit=1)

            if not category:
                category = self.env['product.category'].create({
                    'name': 'IT Services',
                })

            product = self.env['product.template'].create({
                'name': service_catalog.name,
                'default_code': f"SRV_{service_catalog.code}",
                'type': 'service',
                'invoice_policy': 'order',
                'list_price': service_catalog.sales_price,
                'categ_id': category.id,
            })
        return product.product_variant_id

    def _calculate_next_run_date(self):
        """Calculate next run date based on billing period"""
        if self.billing_period == 'monthly':
            self.next_run_date = fields.Date.today() + relativedelta(months=1)
        elif self.billing_period == 'quarterly':
            self.next_run_date = fields.Date.today() + relativedelta(months=3)
        else:  # yearly
            self.next_run_date = fields.Date.today() + relativedelta(years=1)

        # Adjust to billing day
        try:
            self.next_run_date = self.next_run_date.replace(day=self.billing_day)
        except ValueError:
            # Handle months with fewer days
            self.next_run_date = self.next_run_date.replace(day=28)

    def _send_notifications(self, invoices, acts):
        """Send notifications to users"""
        subject = f"Billing Automation Complete - {len(invoices)} invoices created"
        body = f"""
Billing automation '{self.name}' has completed successfully.

Summary:
- Invoices created: {len(invoices)}
- Work acts created: {len(acts)}
- Next run date: {self.next_run_date}

Created invoices:
{chr(10).join([f"- {inv.name} ({inv.partner_id.name}): {inv.amount_total}" for inv in invoices])}
"""

        for user in self.notify_user_ids:
            self.env['mail.mail'].create({
                'subject': subject,
                'body_html': body.replace(chr(10), '<br/>'),
                'email_to': user.email,
                'auto_delete': True,
            }).send()

    @api.model
    def cron_run_billing_automations(self):
        """Cron job to run billing automations"""
        automations = self.search([
            ('active', '=', True),
            ('next_run_date', '<=', fields.Date.today())
        ])

        for automation in automations:
            try:
                automation._run_billing()
            except Exception as e:
                # Log error and continue with next automation
                self.env['ir.logging'].create({
                    'name': f'Billing Automation Cron Error: {automation.name}',
                    'type': 'server',
                    'level': 'ERROR',
                    'message': str(e),
                    'func': 'cron_run_billing_automations',
                    'path': __file__,
                    'line': 0,
                })