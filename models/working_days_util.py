from odoo import models, fields, api
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import logging

_logger = logging.getLogger(__name__)


class WorkingDaysUtil(models.AbstractModel):
    """Utility for calculating working days in periods"""
    _name = 'working.days.util'
    _description = 'Working Days Calculation Utility'

    @api.model
    def get_working_days_in_month(self, year, month, calendar_id=None):
        """
        Calculate working days in a specific month

        :param year: Year (int)
        :param month: Month (1-12)
        :param calendar_id: Resource calendar ID (optional)
        :return: Number of working days (float)
        """
        if not calendar_id:
            calendar_id = self._get_default_calendar()

        # Get first and last day of month
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        # Use resource calendar to calculate working days
        resource_calendar = self.env['resource.calendar'].browse(calendar_id)

        # Convert to datetime for resource calendar
        start_datetime = datetime.combine(first_day, datetime.min.time())
        end_datetime = datetime.combine(last_day, datetime.max.time())

        # Count working days using simplified approach
        working_days = 0
        current_date = first_day

        while current_date <= last_day:
            # Check if this day is a working day
            day_of_week = str(current_date.weekday())  # Monday = 0, Sunday = 6

            # Check if there's an attendance for this day
            attendance = resource_calendar.attendance_ids.filtered(
                lambda att: att.dayofweek == day_of_week
            )

            if attendance:
                working_days += 1

            current_date += timedelta(days=1)

        return float(working_days)

    @api.model
    def get_working_hours_in_month(self, year, month, calendar_id=None):
        """
        Calculate working hours in a specific month

        :param year: Year (int)
        :param month: Month (1-12)
        :param calendar_id: Resource calendar ID (optional)
        :return: Number of working hours (float)
        """
        if not calendar_id:
            calendar_id = self._get_default_calendar()

        # Get first and last day of month
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        # Use resource calendar to calculate working hours
        resource_calendar = self.env['resource.calendar'].browse(calendar_id)

        total_hours = 0
        current_date = first_day

        while current_date <= last_day:
            # Check if this day is a working day
            day_of_week = str(current_date.weekday())  # Monday = 0, Sunday = 6

            # Get all attendances for this day
            attendances = resource_calendar.attendance_ids.filtered(
                lambda att: att.dayofweek == day_of_week
            )

            # Sum hours for this day
            for attendance in attendances:
                duration = attendance.hour_to - attendance.hour_from
                total_hours += duration

            current_date += timedelta(days=1)

        return total_hours

    @api.model
    def get_working_days_in_period(self, start_date, end_date, calendar_id=None):
        """
        Calculate working days in a date range

        :param start_date: Start date (date object)
        :param end_date: End date (date object)
        :param calendar_id: Resource calendar ID (optional)
        :return: Number of working days (float)
        """
        if not calendar_id:
            calendar_id = self._get_default_calendar()

        resource_calendar = self.env['resource.calendar'].browse(calendar_id)

        working_days = 0
        current_date = start_date

        while current_date <= end_date:
            # Check if this day is a working day
            day_of_week = str(current_date.weekday())  # Monday = 0, Sunday = 6

            # Check if there's an attendance for this day
            attendance = resource_calendar.attendance_ids.filtered(
                lambda att: att.dayofweek == day_of_week
            )

            if attendance:
                working_days += 1

            current_date += timedelta(days=1)

        return float(working_days)

    @api.model
    def _get_default_calendar(self):
        """Get default resource calendar for the company"""
        # 1. Попробовать календарь компании
        calendar = self.env.company.resource_calendar_id

        if calendar:
            return calendar.id

        # 2. Поискать любой активный календарь этой компании
        calendar = self.env['resource.calendar'].search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if calendar:
            # Рекомендуем установить как календарь компании
            try:
                self.env.company.resource_calendar_id = calendar.id
                self.env.cr.commit()
            except:
                pass  # Если нет прав - не критично
            return calendar.id

        # 3. Поискать любой календарь в системе
        calendar = self.env['resource.calendar'].search([], limit=1)

        if calendar:
            return calendar.id

        # 4. В крайнем случае создать базовый календарь
        calendar = self._create_minimal_calendar()

        # Уведомить администратора
        self._notify_calendar_created()

        return calendar.id

    @api.model
    def _notify_calendar_created(self):
        """Write message to company chatter"""
        message = """
        <p>📅 <strong>Cost Allocation: Создан рабочий календарь</strong></p>
        <p>Автоматически создан рабочий календарь для расчета рабочих дней.</p>
        <div class="alert alert-info">
            <p><strong>Рекомендация:</strong> настройте календарь компании в 
            <em>Settings → Companies → Working Times</em> 
            чтобы учесть ваш реальный график работы:</p>
            <ul>
                <li>Рабочие часы (например, 8:30-17:30 с обедом)</li>
                <li>Праздничные дни</li>
                <li>Особые дни и перерывы</li>
            </ul>
        </div>
        """

        try:
            # Записываем в чаттер компании
            self.env.company.message_post(
                body=message,
                subject="Cost Allocation: Создан рабочий календарь",
                message_type='notification'
            )
        except Exception as e:
            # Если не получается в чаттер - записываем в лог
            _logger.warning(f"Не удалось записать в чаттер компании: {e}")
            _logger.info("📅 Cost Allocation: Автоматически создан рабочий календарь для расчета рабочих дней.")
            pass

    @api.model
    def _create_minimal_calendar(self):
        """Create minimal working calendar only as last resort"""
        # Используем настройки по умолчанию из системы
        calendar = self.env['resource.calendar'].create({
            'name': 'Default Working Calendar',
            'company_id': self.env.company.id,
            'tz': self.env.user.tz or self.env.company.partner_id.tz or 'UTC',
        })

        # Добавляем стандартный график понедельник-пятница
        # БЕЗ ХАРДКОДА часов - используем стандартные значения Odoo
        weekdays = [
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday')
        ]

        for day_code, day_name in weekdays:
            self.env['resource.calendar.attendance'].create({
                'calendar_id': calendar.id,
                'dayofweek': day_code,
                'hour_from': 8.0,  # 8:00 - более стандартное время
                'hour_to': 17.0,  # 17:00 - 8 часов рабочий день
                'name': f'{day_name}'
            })

        return calendar

    @api.model
    def get_current_month_working_days(self):
        """Get working days for current month"""
        today = fields.Date.today()
        return self.get_working_days_in_month(today.year, today.month)

    @api.model
    def get_current_month_working_hours(self):
        """Get working hours for current month"""
        today = fields.Date.today()
        return self.get_working_hours_in_month(today.year, today.month)

    # ДОБАВЛЕНО: Кеширование для производительности
    @api.model
    def update_working_days_cache(self):
        """Update working days cache for next few months"""
        today = fields.Date.today()

        # Cache next 6 months
        for i in range(6):
            target_date = today + relativedelta(months=i)
            cache_key = f"working_days_{target_date.year}_{target_date.month}"

            # Calculate and cache
            working_days = self.get_working_days_in_month(target_date.year, target_date.month)
            working_hours = self.get_working_hours_in_month(target_date.year, target_date.month)

            # Store in ir.config_parameter for simple caching
            self.env['ir.config_parameter'].sudo().set_param(
                f'cost_allocation.cache.{cache_key}_days', str(working_days)
            )
            self.env['ir.config_parameter'].sudo().set_param(
                f'cost_allocation.cache.{cache_key}_hours', str(working_hours)
            )

    @api.model
    def get_cached_working_days(self, year, month):
        """Get cached working days or calculate if not cached"""
        cache_key = f"working_days_{year}_{month}"
        cached_value = self.env['ir.config_parameter'].sudo().get_param(
            f'cost_allocation.cache.{cache_key}_days'
        )

        if cached_value:
            return float(cached_value)
        else:
            # Calculate and cache
            working_days = self.get_working_days_in_month(year, month)
            self.env['ir.config_parameter'].sudo().set_param(
                f'cost_allocation.cache.{cache_key}_days', str(working_days)
            )
            return working_days

    @api.model
    def get_cached_working_hours(self, year, month):
        """Get cached working hours or calculate if not cached"""
        cache_key = f"working_days_{year}_{month}"
        cached_value = self.env['ir.config_parameter'].sudo().get_param(
            f'cost_allocation.cache.{cache_key}_hours'
        )

        if cached_value:
            return float(cached_value)
        else:
            # Calculate and cache
            working_hours = self.get_working_hours_in_month(year, month)
            self.env['ir.config_parameter'].sudo().set_param(
                f'cost_allocation.cache.{cache_key}_hours', str(working_hours)
            )
            return working_hours