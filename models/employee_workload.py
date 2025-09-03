# models/employee_workload.py

from odoo import models, fields, api


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
                record.display_name = 'New Workload Record'

    @api.depends('pool_allocation_ids.percentage')
    def _compute_pool_totals(self):
        for workload in self:
            workload.total_pool_percentage = sum(workload.pool_allocation_ids.mapped('percentage'))

    @api.depends('employee_id', 'period_date')
    def _compute_workload(self):
        for record in self:
            if not record.employee_id:
                record.active_services_count = 0
                record.total_workload_factor = 0.0
                record.workload_by_category = ''
                record.is_overloaded = False
                record.overload_percentage = 0.0
                continue

            # Получаем активные сервисы, где сотрудник ответственный
            active_services = self.env['client.service'].search([
                ('responsible_employee_id', '=', record.employee_id.id),
                ('status', '=', 'active')
            ])

            record.active_services_count = len(active_services)

            # Подсчитываем общий workload factor
            total_workload = sum(active_services.mapped('effective_workload_factor'))
            record.total_workload_factor = total_workload

            # Группируем по категориям
            categories = {}
            for service in active_services:
                category = service.category_id.name if service.category_id else 'Uncategorized'
                if category not in categories:
                    categories[category] = 0
                categories[category] += service.effective_workload_factor

            # Формируем текст распределения
            workload_lines = []
            for category, workload in categories.items():
                workload_lines.append(f"{category}: {workload:.1f}")
            record.workload_by_category = "\n".join(workload_lines)

            # Проверяем перегрузку
            if record.target_workload > 0:
                record.overload_percentage = (total_workload / record.target_workload - 1) * 100
                record.is_overloaded = total_workload > record.target_workload
            else:
                record.overload_percentage = 0.0
                record.is_overloaded = False


class EmployeePoolWorkload(models.Model):
    _name = 'employee.pool.workload'
    _description = 'Employee Pool Workload Allocation'
    _rec_name = 'display_name'

    workload_id = fields.Many2one('employee.workload', string='Workload Record', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', related='workload_id.employee_id', store=True)
    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True)
    percentage = fields.Float(string='Allocation %', default=0.0,
                              help='Percentage of time allocated to this pool')

    display_name = fields.Char(string='Display Name', compute='_compute_display_name')

    @api.depends('pool_id', 'percentage')
    def _compute_display_name(self):
        for record in self:
            if record.pool_id:
                record.display_name = f"{record.pool_id.name} ({record.percentage}%)"
            else:
                record.display_name = f"Allocation ({record.percentage}%)"

    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise models.ValidationError("Percentage must be between 0 and 100")

    @api.model
    def create(self, vals):
        # Проверяем, чтобы общий процент не превышал 100%
        result = super().create(vals)
        workload = result.workload_id
        if workload.total_pool_percentage > 100:
            raise models.ValidationError(
                f"Total allocation percentage ({workload.total_pool_percentage}%) cannot exceed 100%"
            )
        return result

    def write(self, vals):
        result = super().write(vals)
        if 'percentage' in vals:
            for record in self:
                workload = record.workload_id
                if workload.total_pool_percentage > 100:
                    raise models.ValidationError(
                        f"Total allocation percentage ({workload.total_pool_percentage}%) cannot exceed 100%"
                    )
        return result