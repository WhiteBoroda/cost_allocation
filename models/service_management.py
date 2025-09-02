from odoo import models, fields, api


class ServiceType(models.Model):
    _name = 'service.type'
    _description = 'Service Type'
    _order = 'category_id, sequence, name'
    _inherit = ['sequence.helper']

    name = fields.Char(string='Service Name', required=True)
    code = fields.Char(string='Code', readonly=True, copy=False)
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

    # ИЗМЕНЕНО: заменил unit_name на Many2one поле
    unit_id = fields.Many2one('unit.of.measure', string='Unit of Measure', required=True)

    base_price = fields.Float(string='Base Price per Unit')

    # REMOVED: support_level - moved to res.partner (client-specific)
    # support_level = fields.Selection([...], ...)  -- УДАЛЕНО

    # Base SLA (will be adjusted per client support level)
    response_time = fields.Float(string='Base Response Time (hours)', default=24.0,
                                 help='Base response time - actual SLA determined by client support level')
    resolution_time = fields.Float(string='Base Resolution Time (hours)', default=72.0,
                                   help='Base resolution time - actual SLA determined by client support level')
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
                                   help='Base complexity/time factor - will be adjusted by client support level')

    # Skills required
    required_skill_ids = fields.Many2many('hr.skill', string='Required Skills',
                                          help='Required skills for this service type (if HR Skills module is installed)')

    # Statistics
    active_services_count = fields.Integer(string='Active Services', compute='_compute_service_count')

    # Status - ДОБАВЛЕНО: недостающее поле active
    active = fields.Boolean(string='Active', default=True)

    # Company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends('name')  # зависимость нужно будет проверить в полном файле
    def _compute_service_count(self):
        for service_type in self:
            # Подсчитываем активные сервисы этого типа
            service_type.active_services_count = self.env['client.service'].search_count([
                ('service_type_id', '=', service_type.id),
                ('status', '=', 'active')
            ])

    def get_effective_workload_factor(self, client_support_level='standard'):
        """Get workload factor adjusted by client support level"""
        self.ensure_one()

        support_multiplier = {
            'basic': 0.8,  # Меньше внимания
            'standard': 1.0,  # Базовый уровень
            'premium': 1.3,  # Больше внимания
            'enterprise': 1.6,  # Максимальное внимание
        }

        multiplier = support_multiplier.get(client_support_level, 1.0)
        return self.workload_factor * multiplier

    def get_sla_for_client(self, client):
        """Get SLA adjusted for specific client support level"""
        self.ensure_one()
        if not client:
            return {
                'response_time': self.response_time,
                'resolution_time': self.resolution_time,
                'availability_sla': self.availability_sla
            }

        # Client SLA определяется support_level клиента
        client_sla = client.get_sla_for_service_type(self)

        return {
            'response_time': client_sla['response_time'],
            'resolution_time': client_sla['resolution_time'],
            'availability_sla': self.availability_sla  # Availability остается базовой
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('service.type.code')
        return super().create(vals_list)


class ClientService(models.Model):
    _name = 'client.service'
    _description = 'Client IT Services and Equipment'
    _rec_name = 'display_name'
    _inherit = ['sequence.helper']  # ДОБАВЛЕНО: наследование для автогенерации кодов

    # ДОБАВЛЕНО: поле кода для client.service
    code = fields.Char(string='Service Code', readonly=True, copy=False)
    client_id = fields.Many2one('res.partner', string='Client',
                                domain=[('is_company', '=', True)], required=True)
    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)

    category_id = fields.Many2one('service.category', string='Category',
                                  related='service_type_id.category_id', store=True, readonly=True)

    # SLA computed from client support level and service type
    effective_response_time = fields.Float(string='Response Time (hours)',
                                           compute='_compute_effective_sla', store=True)
    effective_resolution_time = fields.Float(string='Resolution Time (hours)',
                                             compute='_compute_effective_sla', store=True)
    effective_workload_factor = fields.Float(string='Effective Workload Factor',
                                             compute='_compute_effective_workload', store=True)

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
    auto_assigned = fields.Boolean(string='Auto Assigned', readonly=True,
                                   help='This service was auto-assigned based on service type settings')

    # Pricing (per unit/month)
    monthly_cost = fields.Float(string='Monthly Cost per Unit',
                                help='Cost per unit per month for this service')

    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)

    # Status and lifecycle
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', required=True)

    # Service history
    notes = fields.Html(string='Service Notes')

    # Computed fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    total_monthly_cost = fields.Float(string='Total Monthly Cost',
                                      compute='_compute_total_monthly_cost', store=True)

    # ИСПРАВЛЕНО: добавлено поле company_id
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    # Cost Driver связи
    related_driver_values = fields.One2many('client.cost.driver', 'client_id',
                                            string='Related Cost Driver Values',
                                            domain="[('client_id', '=', client_id)]")

    @api.depends('client_id.support_level', 'service_type_id.response_time', 'service_type_id.resolution_time')
    def _compute_effective_sla(self):
        """Compute effective SLA based on client support level"""
        for service in self:
            if service.client_id and service.service_type_id:
                sla = service.service_type_id.get_sla_for_client(service.client_id)
                service.effective_response_time = sla['response_time']
                service.effective_resolution_time = sla['resolution_time']
            else:
                service.effective_response_time = service.service_type_id.response_time if service.service_type_id else 24.0
                service.effective_resolution_time = service.service_type_id.resolution_time if service.service_type_id else 72.0

    @api.depends('client_id.support_level', 'service_type_id.workload_factor')
    def _compute_effective_workload(self):
        """Compute effective workload factor including client support level"""
        for service in self:
            if service.client_id and service.service_type_id:
                service.effective_workload_factor = service.client_id.get_effective_workload_factor(
                    service.service_type_id.workload_factor)
            else:
                service.effective_workload_factor = service.service_type_id.workload_factor if service.service_type_id else 1.0

    @api.depends('name', 'service_type_id', 'client_id', 'location')
    def _compute_display_name(self):
        for service in self:
            name_parts = []
            if service.name:
                name_parts.append(service.name)
            elif service.service_type_id:
                name_parts.append(service.service_type_id.name)

            if service.location:
                name_parts.append(f"({service.location})")

            service.display_name = ' '.join(name_parts) if name_parts else 'New Service'

    @api.depends('monthly_cost', 'quantity')
    def _compute_total_monthly_cost(self):
        for service in self:
            service.total_monthly_cost = service.monthly_cost * service.quantity

    @api.onchange('service_type_id')
    def _onchange_service_type(self):
        """Auto-assign team when service type changes"""
        if self.service_type_id:
            # Auto-assign if design is enabled
            if self.service_type_id.auto_assign_responsible:
                if self.service_type_id.primary_responsible_id:
                    self.responsible_employee_id = self.service_type_id.primary_responsible_id
                if self.service_type_id.default_responsible_ids:
                    self.support_team_ids = self.service_type_id.default_responsible_ids

            # Set default name if empty
            if not self.name:
                self.name = self.service_type_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('client.service.code')
        return super().create(vals_list)

    def action_activate(self):
        """Activate service"""
        for service in self:
            service.status = 'active'


    def action_set_inactive(self):
        """Set service inactive"""
        for service in self:
            service.status = 'inactive'


    def action_set_maintenance(self):
        """Set service under maintenance"""
        for service in self:
            service.status = 'maintenance'



class EmployeeWorkload(models.Model):
    _name = 'employee.workload'
    _description = 'Employee Workload Tracking'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    period_date = fields.Date(string='Period', required=True, default=fields.Date.today)

    # Services assigned
    active_services_count = fields.Integer(string='Active Services', compute='_compute_workload')
    total_workload_factor = fields.Float(string='Total Workload Factor', compute='_compute_workload',
                                         help='Sum of effective workload factors (includes client support levels)')

    # Categories breakdown
    workload_by_category = fields.Text(string='Workload by Category', compute='_compute_workload')

    # Status
    is_overloaded = fields.Boolean(string='Overloaded', compute='_compute_workload',
                                   help='Employee has more than optimal workload')
    overload_percentage = fields.Float(string='Overload %', compute='_compute_workload')

    # Target workload (configurable per employee)
    target_workload = fields.Float(string='Target Workload', default=100.0,
                                   help='Target workload factor for this employee')

    @api.depends('employee_id', 'period_date')
    def _compute_workload(self):
        for workload in self:
            # Get active services for this employee
            services = self.env['client.service'].search([
                ('responsible_employee_id', '=', workload.employee_id.id),
                ('status', '=', 'active')
            ])

            workload.active_services_count = len(services)

            # Calculate total workload factor using EFFECTIVE workload (includes client support level)
            total_factor = sum(services.mapped('effective_workload_factor'))
            workload.total_workload_factor = total_factor

            # Calculate overload
            if workload.target_workload > 0:
                workload.overload_percentage = (total_factor / workload.target_workload) * 100
                workload.is_overloaded = workload.overload_percentage > 100
            else:
                workload.overload_percentage = 0
                workload.is_overloaded = False

            # Workload by category (using effective factors)
            category_workload = {}
            for service in services:
                category = service.category_id.name if service.category_id else 'Uncategorized'
                factor = service.effective_workload_factor
                category_workload[category] = category_workload.get(category, 0) + factor

            workload_text = '\n'.join([f"{cat}: {factor}" for cat, factor in category_workload.items()])
            workload.workload_by_category = workload_text

    @api.model
    def update_all_workloads(self):
        """Update workload for all employees - called by cron"""
        employees = self.env['hr.employee'].search([])
        today = fields.Date.today()

        for employee in employees:
            # Check if workload record exists for this month
            existing = self.search([
                ('employee_id', '=', employee.id),
                ('period_date', '=', today)
            ])

            if not existing:
                self.create({
                    'employee_id': employee.id,
                    'period_date': today
                })
            else:
                # Force recompute
                existing._compute_workload()