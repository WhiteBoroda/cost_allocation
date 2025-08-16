from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class ServiceCategory(models.Model):
    _name = 'service.category'
    _description = 'IT Service Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    cost_pool_id = fields.Many2one('cost.pool', string='Related Cost Pool')

    # Responsible employees for this category
    default_responsible_ids = fields.Many2many('hr.employee',
                                               'category_employee_rel',
                                               'category_id', 'employee_id',
                                               string='Default Responsible Team')
    primary_responsible_id = fields.Many2one('hr.employee', string='Primary Responsible')

    # Statistics
    service_type_count = fields.Integer(string='Service Types', compute='_compute_counts')
    active_services_count = fields.Integer(string='Active Services', compute='_compute_counts')

    active = fields.Boolean(default=True)

    @api.depends('name')
    def _compute_counts(self):
        for category in self:
            category.service_type_count = len(self.env['service.type'].search([('category_id', '=', category.id)]))
            category.active_services_count = len(self.env['client.service'].search([
                ('service_type_id.category_id', '=', category.id),
                ('status', '=', 'active')
            ]))

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Category code must be unique!')
    ]


class ServiceType(models.Model):
    _name = 'service.type'
    _description = 'IT Service Type'
    _order = 'category_id, sequence, name'

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Code', required=True)
    category_id = fields.Many2one('service.category', string='Category', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')

    # Pricing
    service_type = fields.Selection([
        ('equipment', 'Equipment Based'),
        ('user', 'User Based'),
        ('fixed', 'Fixed Price'),
        ('consumption', 'Consumption Based')
    ], string='Billing Type', required=True, default='equipment')

    unit_name = fields.Char(string='Unit Name', default='Unit')
    base_price = fields.Float(string='Base Price per Unit')

    # Technical details
    support_level = fields.Selection([
        ('basic', 'Basic Support'),
        ('standard', 'Standard Support'),
        ('premium', 'Premium Support'),
        ('enterprise', 'Enterprise Support')
    ], string='Support Level', default='standard')

    # SLA
    response_time = fields.Float(string='Response Time (hours)', default=24.0)
    resolution_time = fields.Float(string='Resolution Time (hours)', default=72.0)
    availability_sla = fields.Float(string='Availability SLA (%)', default=99.0)

    # Responsible employees
    default_responsible_ids = fields.Many2many('hr.employee',
                                               'service_type_employee_rel',
                                               'service_type_id', 'employee_id',
                                               string='Default Support Team')
    primary_responsible_id = fields.Many2one('hr.employee', string='Primary Responsible')

    # Auto-assignment rules
    auto_assign_responsible = fields.Boolean(string='Auto Assign to New Services', default=True)
    workload_factor = fields.Float(string='Workload Factor', default=1.0,
                                   help='Relative complexity/time factor for this service type')

    # Skills required
    required_skill_ids = fields.Many2many('hr.skill', string='Required Skills',
                                          help='Required skills for this service type (if HR Skills module is installed)')

    # Statistics
    active_services_count = fields.Integer(string='Active Services', compute='_compute_service_count')

    active = fields.Boolean(default=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('name')
    def _compute_service_count(self):
        for service_type in self:
            service_type.active_services_count = len(self.env['client.service'].search([
                ('service_type_id', '=', service_type.id),
                ('status', '=', 'active')
            ]))

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            # Inherit responsible team from category
            if self.category_id.default_responsible_ids:
                self.default_responsible_ids = self.category_id.default_responsible_ids
            if self.category_id.primary_responsible_id:
                self.primary_responsible_id = self.category_id.primary_responsible_id

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Service code must be unique!')
    ]


class ClientService(models.Model):
    _name = 'client.service'
    _description = 'Client IT Services and Equipment'
    _rec_name = 'display_name'

    client_id = fields.Many2one('res.partner', string='Client',
                                domain=[('is_company', '=', True)], required=True)
    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)

    # Equipment/Service details
    name = fields.Char(string='Equipment/Service Name')
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)

    # Location and technical data
    location = fields.Char(string='Location')
    ip_address = fields.Char(string='IP Address')
    mac_address = fields.Char(string='MAC Address')
    serial_number = fields.Char(string='Serial Number')
    inventory_number = fields.Char(string='Inventory Number')

    # Service details
    installation_date = fields.Date(string='Installation Date')
    warranty_end = fields.Date(string='Warranty End')
    last_maintenance = fields.Date(string='Last Maintenance')
    next_maintenance = fields.Date(string='Next Maintenance')

    # Responsible team - specific for this service/equipment
    responsible_employee_id = fields.Many2one('hr.employee', string='Primary Responsible')
    support_team_ids = fields.Many2many('hr.employee',
                                        'client_service_employee_rel',
                                        'service_id', 'employee_id',
                                        string='Support Team')

    # Auto-assign from service type
    auto_assigned = fields.Boolean(string='Auto Assigned from Service Type', default=False)

    # Status
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired')
    ], string='Status', default='active', required=True)

    # Subscription link
    subscription_line_id = fields.Many2one('service.subscription.line', string='Subscription Line')

    # Display name
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    # Cost driver integration
    driver_quantity = fields.Float(string='Driver Quantity', compute='_compute_driver_quantity', store=True)

    # Workload estimation
    estimated_monthly_hours = fields.Float(string='Estimated Monthly Hours',
                                           compute='_compute_workload', store=True)

    active = fields.Boolean(default=True)

    @api.depends('name', 'service_type_id', 'client_id')
    def _compute_display_name(self):
        for record in self:
            if record.name:
                record.display_name = f"{record.client_id.name} - {record.name}"
            else:
                record.display_name = f"{record.client_id.name} - {record.service_type_id.name}"

    @api.depends('quantity', 'status', 'service_type_id')
    def _compute_driver_quantity(self):
        for record in self:
            if record.status == 'active':
                record.driver_quantity = record.quantity
            else:
                record.driver_quantity = 0.0

    @api.depends('service_type_id.workload_factor', 'quantity')
    def _compute_workload(self):
        for record in self:
            if record.service_type_id.workload_factor and record.quantity:
                # Base monthly hours per unit * workload factor * quantity
                base_hours = 2.0  # Default 2 hours per month per unit
                record.estimated_monthly_hours = base_hours * record.service_type_id.workload_factor * record.quantity
            else:
                record.estimated_monthly_hours = 0.0

    @api.onchange('service_type_id')
    def _onchange_service_type_id(self):
        if self.service_type_id and self.service_type_id.auto_assign_responsible:
            # Auto-assign responsible team from service type
            if self.service_type_id.primary_responsible_id:
                self.responsible_employee_id = self.service_type_id.primary_responsible_id
            if self.service_type_id.default_responsible_ids:
                self.support_team_ids = self.service_type_id.default_responsible_ids
            self.auto_assigned = True

    @api.model
    def update_cost_drivers(self):
        """Update cost driver quantities based on active services"""
        # Group services by client and service type
        service_data = {}

        for service in self.search([('status', '=', 'active')]):
            client = service.client_id
            service_type = service.service_type_id

            key = (client.id,
                   service_type.category_id.cost_pool_id.id if service_type.category_id.cost_pool_id else None)

            if key not in service_data:
                service_data[key] = 0
            service_data[key] += service.driver_quantity

        # Update cost drivers
        for (client_id, pool_id), quantity in service_data.items():
            if pool_id:
                driver = self.env['cost.driver'].search([('pool_id', '=', pool_id)], limit=1)
                if driver:
                    client_driver = self.env['client.cost.driver'].search([
                        ('driver_id', '=', driver.id),
                        ('client_id', '=', client_id)
                    ])

                    if client_driver:
                        client_driver.quantity = quantity
                    else:
                        self.env['client.cost.driver'].create({
                            'driver_id': driver.id,
                            'client_id': client_id,
                            'quantity': quantity
                        })


class EmployeeWorkload(models.Model):
    _name = 'employee.workload'
    _description = 'Employee Workload Analysis'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    period_date = fields.Date(string='Period', default=fields.Date.today, required=True)

    # Calculated workload
    total_estimated_hours = fields.Float(string='Total Estimated Hours', compute='_compute_workload')
    total_services = fields.Integer(string='Total Services', compute='_compute_workload')
    primary_services = fields.Integer(string='Primary Responsible', compute='_compute_workload')
    support_services = fields.Integer(string='Support Team Member', compute='_compute_workload')

    # Workload by category
    workload_by_category = fields.Text(string='Workload by Category', compute='_compute_workload')

    # Capacity planning
    available_hours = fields.Float(string='Available Hours per Month', default=160.0)
    utilization_percentage = fields.Float(string='Utilization %', compute='_compute_utilization')
    overloaded = fields.Boolean(string='Overloaded', compute='_compute_utilization')

    @api.depends('employee_id', 'period_date')
    def _compute_workload(self):
        for record in self:
            # Services where employee is primary responsible
            primary_services = self.env['client.service'].search([
                ('responsible_employee_id', '=', record.employee_id.id),
                ('status', '=', 'active')
            ])

            # Services where employee is in support team
            support_services = self.env['client.service'].search([
                ('support_team_ids', 'in', record.employee_id.id),
                ('status', '=', 'active')
            ])

            record.primary_services = len(primary_services)
            record.support_services = len(support_services)
            record.total_services = len(primary_services | support_services)

            # Calculate estimated hours
            total_hours = sum(primary_services.mapped('estimated_monthly_hours'))
            # Support team members get 30% of the workload
            total_hours += sum(support_services.mapped('estimated_monthly_hours')) * 0.3

            record.total_estimated_hours = total_hours

            # Workload by category
            categories = {}
            for service in primary_services | support_services:
                cat_name = service.service_type_id.category_id.name
                if cat_name not in categories:
                    categories[cat_name] = 0
                categories[cat_name] += 1

            record.workload_by_category = '\n'.join([f"{cat}: {count} services" for cat, count in categories.items()])

    @api.depends('total_estimated_hours', 'available_hours')
    def _compute_utilization(self):
        for record in self:
            if record.available_hours > 0:
                record.utilization_percentage = (record.total_estimated_hours / record.available_hours) * 100
                record.overloaded = record.utilization_percentage > 100
            else:
                record.utilization_percentage = 0
                record.overloaded = False

    _sql_constraints = [
        ('unique_employee_period', 'unique(employee_id, period_date)',
         'Employee workload record must be unique per period!')
    ]

    @api.model
    def update_all_workloads(self, period_date=None):
        """Update workload for all employees for given period"""
        if not period_date:
            period_date = fields.Date.today()

        # Get all employees from cost.employee
        employees = self.env['cost.employee'].search([('active', '=', True)])

        for emp_cost in employees:
            # Check if workload record exists
            workload = self.search([
                ('employee_id', '=', emp_cost.employee_id.id),
                ('period_date', '=', period_date)
            ])

            if not workload:
                # Create new workload record
                self.create({
                    'employee_id': emp_cost.employee_id.id,
                    'period_date': period_date,
                })
            else:
                # Trigger recomputation
                workload._compute_workload()
                workload._compute_utilization()


class ServiceSubscription(models.Model):
    _name = 'service.subscription'
    _description = 'IT Service Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Subscription Name', required=True, tracking=True)
    client_id = fields.Many2one('res.partner', string='Client',
                                domain=[('is_company', '=', True)], required=True, tracking=True)

    # Subscription details
    start_date = fields.Date(string='Start Date', default=fields.Date.today, required=True, tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)

    # Billing
    billing_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], string='Billing Period', default='monthly', required=True, tracking=True)

    next_invoice_date = fields.Date(string='Next Invoice Date', tracking=True)
    auto_renew = fields.Boolean(string='Auto Renew', default=True, tracking=True)

    # Services
    service_line_ids = fields.One2many('service.subscription.line', 'subscription_id', string='Services')

    # Totals
    monthly_total = fields.Float(string='Monthly Total', compute='_compute_totals', store=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_totals', store=True)
    total_price = fields.Float(string='Total Price', compute='_compute_totals', store=True)
    margin = fields.Float(string='Margin %', compute='_compute_totals', store=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', tracking=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('service_line_ids.monthly_cost', 'service_line_ids.monthly_price')
    def _compute_totals(self):
        for subscription in self:
            subscription.monthly_total = sum(subscription.service_line_ids.mapped('monthly_price'))
            subscription.total_cost = sum(subscription.service_line_ids.mapped('monthly_cost'))
            subscription.total_price = sum(subscription.service_line_ids.mapped('monthly_price'))

            if subscription.total_cost > 0:
                subscription.margin = ((
                                                   subscription.total_price - subscription.total_cost) / subscription.total_price) * 100
            else:
                subscription.margin = 0

    def action_activate(self):
        self.state = 'active'
        self._update_next_invoice_date()

    def action_suspend(self):
        self.state = 'suspended'

    def action_terminate(self):
        self.state = 'terminated'

    def _update_next_invoice_date(self):
        """Update next invoice date based on billing period"""
        if self.billing_period == 'monthly':
            if self.next_invoice_date:
                self.next_invoice_date = self.next_invoice_date + relativedelta(months=1)
            else:
                self.next_invoice_date = fields.Date.today() + relativedelta(months=1)
        elif self.billing_period == 'quarterly':
            if self.next_invoice_date:
                self.next_invoice_date = self.next_invoice_date + relativedelta(months=3)
            else:
                self.next_invoice_date = fields.Date.today() + relativedelta(months=3)
        else:  # yearly
            if self.next_invoice_date:
                self.next_invoice_date = self.next_invoice_date + relativedelta(years=1)
            else:
                self.next_invoice_date = fields.Date.today() + relativedelta(years=1)


class ServiceSubscriptionLine(models.Model):
    _name = 'service.subscription.line'
    _description = 'Service Subscription Line'

    subscription_id = fields.Many2one('service.subscription', string='Subscription', required=True, ondelete='cascade')
    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)
    name = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)

    # Pricing
    unit_cost = fields.Float(string='Unit Cost', compute='_compute_costs', store=True)
    unit_price = fields.Float(string='Unit Price', required=True)
    monthly_cost = fields.Float(string='Monthly Cost', compute='_compute_costs', store=True)
    monthly_price = fields.Float(string='Monthly Price', compute='_compute_costs', store=True)

    # Links
    client_service_ids = fields.One2many('client.service', 'subscription_line_id', string='Related Services')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('quantity', 'unit_price', 'service_type_id')
    def _compute_costs(self):
        for line in self:
            # Calculate cost from cost allocation
            if line.service_type_id and line.subscription_id.client_id:
                # Get latest allocation for client
                allocation = self.env['client.cost.allocation'].search([
                    ('client_id', '=', line.subscription_id.client_id.id),
                    ('state', '=', 'confirmed')
                ], order='period_date desc', limit=1)

                if allocation:
                    # Calculate proportional cost based on service type
                    line.unit_cost = allocation.total_cost / max(allocation.client_id.service_count or 1, 1)
                else:
                    line.unit_cost = line.service_type_id.base_price * 0.7  # Default 70% cost ratio
            else:
                line.unit_cost = 0

            line.monthly_cost = line.unit_cost * line.quantity
            line.monthly_price = line.unit_price * line.quantity

    def _get_service_product(self):
        """Get or create product for service type"""
        product = self.env['product.template'].search([
            ('default_code', '=', f"SRV_{self.service_type_id.code}")
        ], limit=1)

        if not product:
            product = self.env['product.template'].create({
                'name': self.service_type_id.name,
                'default_code': f"SRV_{self.service_type_id.code}",
                'type': 'service',
                'invoice_policy': 'order',
                'list_price': self.service_type_id.base_price,
                'categ_id': self._get_service_category().id,
            })
        return product.product_variant_id

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