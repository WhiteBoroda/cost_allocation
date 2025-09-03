# models/employee_workload.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError


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

    # СТАТИСТИКА: поля для фильтрации (store=True)
    active_services_count = fields.Integer(string='Active Services',
                                           compute='_compute_workload_stats', store=True)
    total_workload_factor = fields.Float(string='Total Workload Factor',
                                         compute='_compute_workload_stats', store=True)
    is_overloaded = fields.Boolean(string='Overloaded', compute='_compute_workload_stats', store=True,
                                   help='Employee has more than optimal workload')
    overload_percentage = fields.Float(string='Overload %', compute='_compute_workload_stats', store=True)

    # АНАЛИЗ: поля для отображения (без store)
    workload_by_category = fields.Text(string='Workload by Category',
                                       compute='_compute_workload_analysis')

    # Target workload
    target_workload = fields.Float(string='Target Workload', default=100.0,
                                   help='Target workload factor for this employee')

    @api.depends('employee_id', 'period_date')
    def _compute_display_name(self):
        for record in self:
            if record.employee_id and record.period_date:
                record.display_name = f"{record.employee_id.name} - {record.period_date.strftime('%Y-%m')}"
            else:
                record.display_name = 'New Workload Record'

    @api.depends('pool_allocation_ids.percentage')
    def _compute_pool_totals(self):
        for workload_record in self:
            workload_record.total_pool_percentage = sum(workload_record.pool_allocation_ids.mapped('percentage'))

    @api.depends('employee_id', 'period_date', 'target_workload')
    def _compute_workload_stats(self):
        """Вычисляем статистику для фильтрации (store=True)"""
        for record in self:
            if not record.employee_id or not record.period_date:
                record.active_services_count = 0
                record.total_workload_factor = 0.0
                record.is_overloaded = False
                record.overload_percentage = 0.0
                continue

            # Получаем активные сервисы, где сотрудник ответственный
            active_services = self.env['client.service'].search([
                ('responsible_employee_id', '=', record.employee_id.id),
                ('status', '=', 'active')
            ])

            record.active_services_count = len(active_services)
            total_workload = sum(active_services.mapped('effective_workload_factor'))
            record.total_workload_factor = total_workload

            # Расчет перегрузки
            if record.target_workload > 0:
                record.overload_percentage = ((total_workload - record.target_workload) / record.target_workload) * 100
                record.is_overloaded = record.overload_percentage > 20  # 20% порог перегрузки
            else:
                record.overload_percentage = 0.0
                record.is_overloaded = False

    @api.depends('employee_id', 'period_date')
    def _compute_workload_analysis(self):
        """Вычисляем детальный анализ для отображения (без store)"""
        for record in self:
            if not record.employee_id or not record.period_date:
                record.workload_by_category = ''
                continue

            # Получаем активные сервисы
            active_services = self.env['client.service'].search([
                ('responsible_employee_id', '=', record.employee_id.id),
                ('status', '=', 'active')
            ])

            # Группируем по категориям
            categories = {}
            for service in active_services:
                category = service.category_id.name if service.category_id else 'Uncategorized'
                if category not in categories:
                    categories[category] = 0
                categories[category] += service.effective_workload_factor

            # Формируем текст распределения
            workload_lines = []
            for category, workload_value in categories.items():
                workload_lines.append(f"{category}: {workload_value:.1f}")
            record.workload_by_category = '\n'.join(workload_lines)


class EmployeePoolWorkload(models.Model):
    _name = 'employee.pool.workload'
    _description = 'Employee Cost Pool Workload Allocation'

    workload_id = fields.Many2one('employee.workload', string='Workload Record', required=True,
                                  ondelete='cascade')
    employee_id = fields.Many2one(related='workload_id.employee_id', string='Employee',
                                  readonly=True, store=True)
    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True)
    percentage = fields.Float(string='Allocation %', required=True,
                              help='Percentage of employee time allocated to this pool')

    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise ValidationError("Percentage must be between 0 and 100")

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        for record in result:
            workload_record = record.workload_id
            if workload_record.total_pool_percentage > 100:
                raise ValidationError(
                    f"Total allocation percentage ({workload_record.total_pool_percentage}%) cannot exceed 100%"
                )
        return result

    def write(self, vals):
        result = super().write(vals)
        if 'percentage' in vals:
            for record in self:
                workload_record = record.workload_id
                if workload_record.total_pool_percentage > 100:
                    raise ValidationError(
                        f"Total allocation percentage ({workload_record.total_pool_percentage}%) cannot exceed 100%"
                    )
        return result

    @api.model
    def update_workload_from_pools(self):
        """Update employee workload records from cost pool allocations (CRON method)"""
        current_date = fields.Date.today()
        current_month = current_date.replace(day=1)

        # Получаем всех активных сотрудников
        employees = self.env['hr.employee'].search([('active', '=', True)])

        updated_count = 0
        for employee in employees:
            # Ищем или создаем запись workload для текущего месяца
            existing_workload = self.env['employee.workload'].search([
                ('employee_id', '=', employee.id),
                ('period_date', '=', current_month)
            ])

            if not existing_workload:
                self.env['employee.workload'].create({
                    'employee_id': employee.id,
                    'period_date': current_month,
                })
                updated_count += 1

        return updated_count