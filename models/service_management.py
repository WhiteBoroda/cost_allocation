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
    _description = 'Employee Workload Analysis'
    _rec_name = 'display_name'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    period_date = fields.Date(string='Period', required=True, default=fields.Date.today)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    # НОВЫЕ ПОЛЯ: из пулов затрат
    pool_allocation_ids = fields.One2many('employee.pool.workload', 'workload_id',
                                          string='Pool Allocations')
    total_pool_percentage = fields.Float(string='Total Pool %',
                                         compute='_compute_pool_totals', store=True)

    # СУЩЕСТВУЮЩИЕ ПОЛЯ: из сервисов клиентов
    active_services_count = fields.Integer(string='Active Services',
                                           compute='_compute_workload')
    total_workload_factor = fields.Float(string='Total Workload Factor',
                                         compute='_compute_workload')
    workload_by_category = fields.Text(string='Workload by Category',
                                       compute='_compute_workload')

    # Target workload
    target_workload = fields.Float(string='Target Workload', default=100.0,
                                   help='Target workload factor for this employee')

    # Status
    is_overloaded = fields.Boolean(string='Overloaded', compute='_compute_workload',
                                   help='Employee has more than optimal workload')
    overload_percentage = fields.Float(string='Overload %', compute='_compute_workload')

    @api.depends('employee_id', 'period_date')
    def _compute_display_name(self):
        for record in self:
            if record.employee_id and record.period_date:
                record.display_name = f"{record.employee_id.name} - {record.period_date.strftime('%Y-%m')}"
            else:
                record.display_name = "New Workload"

    @api.depends('pool_allocation_ids.percentage')
    def _compute_pool_totals(self):
        """Подсчитать общий процент из пулов"""
        for record in self:
            record.total_pool_percentage = sum(record.pool_allocation_ids.mapped('percentage'))

    @api.depends('employee_id', 'period_date')
    def _compute_workload(self):
        """СУЩЕСТВУЮЩИЙ метод - оставляем для совместимости"""
        for workload in self:
            # Get active services for this employee
            services = self.env['client.service'].search([
                ('responsible_employee_id', '=', workload.employee_id.id),
                ('status', '=', 'active')
            ])

            workload.active_services_count = len(services)

            # Calculate total workload factor
            total_factor = sum(services.mapped('effective_workload_factor'))
            workload.total_workload_factor = total_factor

            # Calculate overload
            if workload.target_workload > 0:
                workload.overload_percentage = (total_factor / workload.target_workload) * 100
                workload.is_overloaded = workload.overload_percentage > 100
            else:
                workload.overload_percentage = 0
                workload.is_overloaded = False

            # Workload by category
            category_workload = {}
            for service in services:
                category = service.category_id.name if service.category_id else 'Uncategorized'
                factor = service.effective_workload_factor
                category_workload[category] = category_workload.get(category, 0) + factor

            workload_text = '\n'.join([f"{cat}: {factor}" for cat, factor in category_workload.items()])
            workload.workload_by_category = workload_text

    @api.model
    def update_workload_from_pools(self):
        """НОВЫЙ МЕТОД: собрать данные из пулов затрат"""
        # Получаем все активные распределения сотрудников по пулам
        pool_allocations = self.env['cost.pool.allocation'].search([])

        # Группируем по сотрудникам
        employees_data = {}
        for allocation in pool_allocations:
            emp_id = allocation.employee_cost_id.employee_id.id
            if emp_id not in employees_data:
                employees_data[emp_id] = []
            employees_data[emp_id].append(allocation)

        # Создаем/обновляем записи Employee Workload
        today = fields.Date.today()
        for emp_id, allocations in employees_data.items():
            # Найти или создать workload для этого сотрудника
            workload = self.search([
                ('employee_id', '=', emp_id),
                ('period_date', '=', today)
            ], limit=1)

            if not workload:
                workload = self.create({
                    'employee_id': emp_id,
                    'period_date': today
                })

            # Удалить старые pool allocations
            workload.pool_allocation_ids.unlink()

            # Создать новые pool allocations
            for allocation in allocations:
                self.env['employee.pool.workload'].create({
                    'workload_id': workload.id,
                    'pool_id': allocation.pool_id.id,
                    'percentage': allocation.percentage,
                    'monthly_cost': allocation.monthly_cost
                })

    @api.model
    def create(self, vals):
        """При создании записи - автоматически заполнить из пулов"""
        result = super().create(vals)
        if result.employee_id:
            result._sync_pool_allocations()
        return result

    def _sync_pool_allocations(self):
        """Синхронизировать распределения из пулов затрат"""
        self.ensure_one()

        # Найти все распределения этого сотрудника по пулам
        pool_allocations = self.env['cost.pool.allocation'].search([
            ('employee_cost_id.employee_id', '=', self.employee_id.id)
        ])

        # Удалить старые
        self.pool_allocation_ids.unlink()

        # Создать новые
        for allocation in pool_allocations:
            self.env['employee.pool.workload'].create({
                'workload_id': self.id,
                'pool_id': allocation.pool_id.id,
                'percentage': allocation.percentage,
                'monthly_cost': allocation.monthly_cost
            })

    def action_update_from_pools(self):
        """Кнопка для ручного обновления из пулов"""
        self.ensure_one()
        self._sync_pool_allocations()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Updated!',
                'message': f'Workload data updated for {self.employee_id.name}',
                'type': 'success',
                'sticky': False,
            }
        }

# НОВАЯ МОДЕЛЬ: для хранения распределений по пулам в Employee Workload
class EmployeePoolWorkload(models.Model):
    _name = 'employee.pool.workload'
    _description = 'Employee Pool Workload Detail'

    workload_id = fields.Many2one('employee.workload', string='Workload',
                                  required=True, ondelete='cascade')
    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True)
    percentage = fields.Float(string='Allocation %', required=True)
    monthly_cost = fields.Float(string='Monthly Cost')

    # Computed поля для отображения
    pool_type = fields.Selection(related='pool_id.pool_type', store=True)
    pool_name = fields.Char(related='pool_id.name', store=True)


# ДОБАВИТЬ в models/cost_pool.py - триггер для обновления Workload при изменении распределений
class CostPoolAllocation(models.Model):
    _inherit = 'cost.pool.allocation'

    @api.model_create_multi
    def create(self, vals_list):
        """При создании - обновить Employee Workload"""
        result = super().create(vals_list)
        self._update_employee_workload()
        return result

    def write(self, vals):
        """При изменении - обновить Employee Workload"""
        result = super().write(vals)
        if any(key in vals for key in ['employee_cost_id', 'percentage', 'monthly_cost']):
            self._update_employee_workload()
        return result

    def unlink(self):
        """При удалении - обновить Employee Workload"""
        employees = self.mapped('employee_cost_id.employee_id')
        result = super().unlink()
        # Обновить workload для затронутых сотрудников
        for emp in employees:
            workload = self.env['employee.workload'].search([
                ('employee_id', '=', emp.id),
                ('period_date', '=', fields.Date.today())
            ], limit=1)
            if workload:
                workload._sync_pool_allocations()
        return result

    def _update_employee_workload(self):
        """Обновить Employee Workload для затронутых сотрудников"""
        employees = self.mapped('employee_cost_id.employee_id')
        for emp in employees:
            # Найти или создать workload
            workload = self.env['employee.workload'].search([
                ('employee_id', '=', emp.id),
                ('period_date', '=', fields.Date.today())
            ], limit=1)

            if not workload:
                workload = self.env['employee.workload'].create({
                    'employee_id': emp.id,
                    'period_date': fields.Date.today()
                })

            workload._sync_pool_allocations()