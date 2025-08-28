# models/cost_driver.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CostDriver(models.Model):
    _name = 'cost.driver'
    _description = 'Cost Driver'
    _rec_name = 'name'
    _inherit = ['sequence.helper']

    name = fields.Char(string='Driver Name', required=True)
    code = fields.Char(string='Driver Code', readonly=True, copy=False)
    description = fields.Text(string='Description')

    # ВАЖНО: Поля должны быть здесь!
    driver_category_id = fields.Many2one('cost.driver.category', string='Category')

    # ИЗМЕНЕНО: заменил unit_name на Many2one поле
    unit_id = fields.Many2one('unit.of.measure', string='Unit of Measure', required=True)
    # Оставлю для обратной совместимости, но deprecated
    unit_name = fields.Char(string='Unit Name', related='unit_id.name', store=False, readonly=True)

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True)

    # DEPRECATED: оставляю для совместимости с существующими представлениями
    unit_of_measure = fields.Selection([
        ('user', 'Users'),
        ('workstation', 'Workstations'),
        ('printer', 'Printers'),
        ('server', 'Servers'),
        ('gb', 'GB Storage'),
        ('license', 'Licenses'),
        ('hour', 'Hours'),
        ('unit', 'Units')
    ], string='Legacy Unit of Measure', help='Deprecated: Use Unit of Measure field instead')

    # Cost calculation
    cost_per_unit = fields.Float(string='Cost per Unit', compute='_compute_cost_per_unit', store=True)
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_totals', store=True)

    # Client allocations
    client_driver_ids = fields.One2many('client.cost.driver', 'driver_id', string='Client Allocations')

    # Status
    active = fields.Boolean(string='Active', default=True)

    # ИСПРАВЛЕНО: Currency с правильными параметрами
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        help='Currency for cost calculations'
    )

    # Company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    @api.depends('pool_id.total_monthly_cost', 'total_quantity')
    def _compute_cost_per_unit(self):
        for driver in self:
            if driver.total_quantity > 0 and driver.pool_id:
                driver.cost_per_unit = driver.pool_id.total_monthly_cost / driver.total_quantity
            else:
                driver.cost_per_unit = 0.0

    @api.depends('client_driver_ids.quantity')
    def _compute_totals(self):
        for driver in self:
            driver.total_quantity = sum(driver.client_driver_ids.mapped('quantity'))

    @api.model_create_multi
    def create(self, vals_list):
        """ИСПРАВЛЕНО: защищаем currency_id при создании"""
        for vals in vals_list:
            # Автогенерация кода
            if not vals.get('code'):
                vals['code'] = self._generate_code('cost.driver.code')

            # ИСПРАВЛЕНО: защита currency_id
            if not vals.get('currency_id'):
                vals['currency_id'] = self.env.company.currency_id.id

            # Если unit_id не задан, но есть unit_of_measure, попытаемся найти подходящую единицу
            if not vals.get('unit_id') and vals.get('unit_of_measure'):
                legacy_unit_mapping = {
                    'user': 'unit_user',
                    'workstation': 'unit_workstation',
                    'printer': 'unit_printer',
                    'server': 'unit_server',
                    'gb': 'unit_gigabyte',
                    'license': 'unit_license',
                    'hour': 'unit_hour',
                    'unit': 'unit_unit'
                }

                unit_ref = legacy_unit_mapping.get(vals['unit_of_measure'])
                if unit_ref:
                    try:
                        unit = self.env.ref(f'cost_allocation.{unit_ref}')
                        vals['unit_id'] = unit.id
                    except:
                        # Если не найдем, оставим как есть
                        pass

        return super().create(vals_list)

    def write(self, vals):
        """ИСПРАВЛЕНО: защищаем currency_id при обновлении"""
        # Запоминаем выбранные пользователем валюты ДО save
        original_currencies = {}
        for record in self:
            if 'currency_id' in vals:
                # Если пользователь явно выбрал валюту - запомним её
                original_currencies[record.id] = vals['currency_id']
            elif record.currency_id:
                # Если валюта уже установлена - тоже запомним
                original_currencies[record.id] = record.currency_id.id

        # Сохраняем изменения
        result = super().write(vals)

        # ВОССТАНАВЛИВАЕМ валюты после compute методов
        if original_currencies:
            for record in self:
                if record.id in original_currencies:
                    expected_currency = original_currencies[record.id]
                    if record.currency_id.id != expected_currency:
                        # Валюта была перезаписана - восстанавливаем
                        super(CostDriver, record).write({'currency_id': expected_currency})

        return result

    @api.constrains('cost_per_unit')
    def _check_cost_per_unit(self):
        for record in self:
            if record.cost_per_unit < 0:
                raise ValidationError("Cost per unit cannot be negative")

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Driver code must be unique!')
    ]


class ClientCostDriver(models.Model):
    _name = 'client.cost.driver'
    _description = 'Client Cost Driver Values'

    driver_id = fields.Many2one('cost.driver', string='Cost Driver', required=True, ondelete='cascade')
    client_id = fields.Many2one('res.partner', string='Client',
                                domain=[('is_company', '=', True)], required=True)
    quantity = fields.Float(string='Quantity', required=True, default=0.0)
    allocated_cost = fields.Float(string='Allocated Cost', compute='_compute_allocated_cost', store=True)

    @api.depends('driver_id.cost_per_unit', 'quantity')
    def _compute_allocated_cost(self):
        for record in self:
            record.allocated_cost = record.driver_id.cost_per_unit * record.quantity

    _sql_constraints = [
        ('unique_driver_client', 'unique(driver_id, client_id)', 'Driver-Client combination must be unique!')
    ]