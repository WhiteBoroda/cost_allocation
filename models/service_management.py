from odoo import models, fields, api


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

    category_id = fields.Many2one('service.category', string='Category',
                                  related='service_type_id.category_id', store=True, readonly=True)

    # Equipment/Service details
    name = fields.Char(string='Equipment/Service Name')
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)

    # Location and technical data
    location = fields.Char(string='Location')
    brand = fields.Char(string='Brand')
    model = fields.Char(string='Model')
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

    # Subscription link - reference to subscription line
    subscription_line_id = fields.Many2one('client.service.subscription.line', string='Subscription Line')

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