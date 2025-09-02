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

    # Category
    driver_category_id = fields.Many2one('cost.driver.category', string='Category')

    # Unit of Measure
    unit_id = fields.Many2one('unit.of.measure', string='Unit of Measure', required=True)

    pool_id = fields.Many2one('cost.pool', string='Cost Pool', required=True)

    # ==================== НОВЫЕ ПОЛЯ ПОКУПКИ ====================
    is_license_unit = fields.Boolean(
        string='Is License Unit',
        compute='_compute_is_license_unit',
        store=True
    )

    # Тип лицензирования
    license_type = fields.Selection([
        ('quantity_based', 'Quantity Based'),
        ('unlimited', 'Unlimited License')
    ], string='License Type', default='quantity_based',
        help='Quantity Based: specific number purchased; Unlimited: fixed cost for unlimited usage')

    # Покупка - ТОЛЬКО для лицензий
    total_purchased_quantity = fields.Float(
        string='Total Purchased Quantity',
        default=0.0,
        help='Total quantity purchased (e.g., 500 Google WorkSpace licenses). For unlimited licenses, leave as 0.'
    )

    purchase_cost = fields.Monetary(
        string='Total Purchase Cost',
        default=0.0,
        currency_field='purchase_currency_id',
        help='Total cost of purchase in original currency'
    )

    purchase_currency_id = fields.Many2one(
        'res.currency',
        string='Purchase Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency in which the purchase was made'
    )

    purchase_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
        ('one_time', 'One Time')
    ], string='Purchase Period', default='monthly',
        help='How often this cost is incurred')

    # Конвертированная стоимость в базовой валюте
    purchase_cost_converted = fields.Monetary(
        string='Purchase Cost (Company Currency)',
        compute='_compute_purchase_cost_converted',
        store=True,
        currency_field='company_currency_id',
        help='Purchase cost converted to company currency'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        store=True
    )

    # Месячная стоимость (для годовых покупок)
    monthly_cost = fields.Monetary(
        string='Monthly Cost',
        compute='_compute_monthly_cost',
        store=True,
        currency_field='company_currency_id',
        help='Monthly cost (annual costs divided by 12)'
    )

    # ==================== НОВЫЕ ПОЛЯ ПРОДАЖ ====================

    # Продажная цена
    markup_percent = fields.Float(
        string='Markup %',
        default=20.0,
        help='Markup percentage for resale (e.g., 20% = sell for 20% more than cost)'
    )

    sales_price_per_unit = fields.Monetary(
        string='Sales Price per Unit',
        compute='_compute_sales_price',
        store=True,
        currency_field='company_currency_id',
        help='Price charged to clients per unit (includes markup)'
    )

    profit_per_unit = fields.Monetary(
        string='Profit per Unit',
        compute='_compute_profit',
        store=True,
        currency_field='company_currency_id',
        help='Profit earned per unit sold'
    )

    total_monthly_profit = fields.Monetary(
        string='Total Monthly Profit',
        compute='_compute_profit',
        store=True,
        currency_field='company_currency_id',
        help='Total profit from allocated units'
    )



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

    # Cost calculation - ИСПРАВЛЕНО
    cost_per_unit = fields.Monetary(
        string='Cost per Unit',
        compute='_compute_cost_per_unit',
        store=True,
        currency_field='currency_id',
        help='Internal cost per unit'
    )
    total_allocated_quantity = fields.Float(string='Allocated Quantity', compute='_compute_totals', store=True,
                                            help='Total quantity allocated to clients')

    unallocated_quantity = fields.Float(
        string='Unallocated Quantity',
        compute='_compute_unallocated_quantity',
        store=True
    )


    # Client allocations
    client_driver_ids = fields.One2many('client.cost.driver', 'driver_id', string='Client Allocations')

    # Status
    active = fields.Boolean(string='Active', default=True)

    # Currency - базовая валюта компании
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        help='Company base currency'
    )

    # Company
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    # ==================== COMPUTED METHODS ====================
    @api.depends('unit_id')
    def _compute_is_license_unit(self):
        """Определяем является ли единица измерения лицензией"""
        for driver in self:
            # Ищем единицу измерения "Лицензия"
            license_unit = self.env.ref('cost_allocation.unit_license', raise_if_not_found=False)
            driver.is_license_unit = license_unit and driver.unit_id == license_unit

    @api.depends('monthly_cost', 'total_purchased_quantity', 'is_license_unit', 'license_type',
                 'total_allocated_quantity')
    def _compute_cost_per_unit(self):
        """Универсальный расчет стоимости за единицу"""
        for driver in self:
            if driver.is_license_unit:
                # Логика для лицензий
                if driver.license_type == 'unlimited':
                    if driver.total_allocated_quantity > 0:
                        driver.cost_per_unit = driver.monthly_cost / driver.total_allocated_quantity
                    else:
                        driver.cost_per_unit = 0.0
                else:  # quantity_based
                    if driver.total_purchased_quantity > 0:
                        driver.cost_per_unit = driver.monthly_cost / driver.total_purchased_quantity
                    else:
                        driver.cost_per_unit = 0.0
            else:
                # Логика для обычных единиц (час, пользователь, сервер и т.д.)
                if driver.total_allocated_quantity > 0:
                    driver.cost_per_unit = driver.monthly_cost / driver.total_allocated_quantity
                else:
                    driver.cost_per_unit = 0.0

    @api.constrains('total_purchased_quantity', 'total_allocated_quantity', 'license_type', 'is_license_unit')
    def _check_quantities(self):
        """Проверки только для лицензий"""
        for driver in self:
            if driver.is_license_unit and driver.license_type == 'quantity_based':
                if (driver.total_purchased_quantity > 0 and
                        driver.total_allocated_quantity > driver.total_purchased_quantity):
                    raise ValidationError(
                        f'Allocated quantity ({driver.total_allocated_quantity}) cannot exceed '
                        f'purchased quantity ({driver.total_purchased_quantity}) for quantity-based licenses'
                    )

    @api.constrains('total_purchased_quantity', 'license_type', 'is_license_unit')
    def _check_unlimited_license(self):
        """Для unlimited лицензий purchased_quantity должно быть 0"""
        for driver in self:
            if (driver.is_license_unit and driver.license_type == 'unlimited' and
                    driver.total_purchased_quantity > 0):
                raise ValidationError(
                    'For unlimited licenses, Total Purchased Quantity should be 0 or empty'
                )

    @api.depends('purchase_cost', 'purchase_currency_id', 'company_currency_id')
    def _compute_purchase_cost_converted(self):
        """Convert purchase cost to company currency"""
        for driver in self:
            if driver.purchase_cost and driver.purchase_currency_id and driver.company_currency_id:
                if driver.purchase_currency_id == driver.company_currency_id:
                    driver.purchase_cost_converted = driver.purchase_cost
                else:
                    # Конвертация валюты по текущему курсу
                    driver.purchase_cost_converted = driver.purchase_currency_id._convert(
                        driver.purchase_cost,
                        driver.company_currency_id,
                        driver.company_id,
                        fields.Date.today()
                    )
            else:
                driver.purchase_cost_converted = 0.0

    @api.depends('purchase_cost_converted', 'purchase_period')
    def _compute_monthly_cost(self):
        """Calculate monthly cost based on purchase period"""
        for driver in self:
            if driver.purchase_cost_converted:
                period_multipliers = {
                    'monthly': 1,
                    'quarterly': 1 / 3,
                    'annual': 1 / 12,
                    'one_time': 1 / 12,  # Амортизируем на год
                }
                multiplier = period_multipliers.get(driver.purchase_period, 1)
                driver.monthly_cost = driver.purchase_cost_converted * multiplier
            else:
                driver.monthly_cost = 0.0

    @api.depends('monthly_cost', 'total_purchased_quantity', 'license_type', 'total_allocated_quantity')
    def _compute_cost_per_unit(self):
        """ИСПРАВЛЕНО: разная логика для quantity-based и unlimited лицензий"""
        for driver in self:
            if driver.license_type == 'unlimited':
                # Для unlimited лицензий: cost per unit = monthly_cost / allocated_quantity
                if driver.total_allocated_quantity > 0:
                    driver.cost_per_unit = driver.monthly_cost / driver.total_allocated_quantity
                else:
                    driver.cost_per_unit = 0.0
            else:
                # Для quantity-based лицензий: cost per unit = monthly_cost / purchased_quantity
                if driver.total_purchased_quantity > 0:
                    driver.cost_per_unit = driver.monthly_cost / driver.total_purchased_quantity
                else:
                    # Fallback на старую логику если не указано купленное количество
                    if driver.total_allocated_quantity > 0 and driver.pool_id:
                        driver.cost_per_unit = driver.pool_id.total_monthly_cost / driver.total_allocated_quantity
                    else:
                        driver.cost_per_unit = 0.0

    @api.depends('cost_per_unit', 'markup_percent')
    def _compute_sales_price(self):
        """Рассчитать продажную цену с наценкой"""
        for driver in self:
            if driver.cost_per_unit and driver.markup_percent:
                driver.sales_price_per_unit = driver.cost_per_unit * (1 + driver.markup_percent / 100)
            else:
                driver.sales_price_per_unit = driver.cost_per_unit

    @api.depends('sales_price_per_unit', 'cost_per_unit', 'total_allocated_quantity')
    def _compute_profit(self):
        """Рассчитать прибыль"""
        for driver in self:
            driver.profit_per_unit = driver.sales_price_per_unit - driver.cost_per_unit
            driver.total_monthly_profit = driver.profit_per_unit * driver.total_allocated_quantity

    @api.depends('client_driver_ids.quantity')
    def _compute_totals(self):
        """Считаем только распределенное количество"""
        for driver in self:
            driver.total_allocated_quantity = sum(driver.client_driver_ids.mapped('quantity'))

    # ==================== VALIDATION ====================

    @api.constrains('total_purchased_quantity', 'license_type')
    def _check_unlimited_license(self):
        """Для unlimited лицензий purchased_quantity должно быть 0"""
        for driver in self:
            if (driver.license_type == 'unlimited' and
                    driver.total_purchased_quantity > 0):
                raise ValidationError(
                    'For unlimited licenses, Total Purchased Quantity should be 0 or empty'
                )

    @api.constrains('unit_id')
    def _check_unit_id(self):
        for driver in self:
            if not driver.unit_id:
                raise ValidationError("Unit of Measure is required for Cost Driver")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('cost.driver.code')
        return super().create(vals_list)

    # ==================== UTILITY METHODS ====================

    @api.depends('total_purchased_quantity', 'total_allocated_quantity', 'is_license_unit', 'license_type')
    def _compute_unallocated_quantity(self):
        for driver in self:
            if driver.is_license_unit and driver.license_type == 'quantity_based':
                unallocated = driver.total_purchased_quantity - driver.total_allocated_quantity
                driver.unallocated_quantity = unallocated
            else:
                driver.unallocated_quantity = 0.0

    def get_unallocated_quantity(self):
        """Получить нераспределенное количество (только для quantity-based)"""
        self.ensure_one()
        if self.is_license_unit and self.license_type == 'quantity_based':
            return self.total_purchased_quantity - self.total_allocated_quantity
        return 0.0

    def get_allocation_percentage(self):
        """Получить процент распределения (только для quantity-based)"""
        self.ensure_one()
        if self.license_type == 'unlimited':
            return 100.0  # Всегда 100% для unlimited
        if self.total_purchased_quantity > 0:
            return (self.total_allocated_quantity / self.total_purchased_quantity) * 100
        return 0.0

    def get_monthly_revenue(self):
        """Получить месячный доход от продаж"""
        self.ensure_one()
        return self.sales_price_per_unit * self.total_allocated_quantity

    def get_cost_efficiency(self):
        """Получить эффективность распределения затрат"""
        self.ensure_one()
        if self.license_type == 'unlimited':
            # Для unlimited: чем больше клиентов, тем эффективнее
            return f"Cost per user: {self.cost_per_unit:.2f} ({self.total_allocated_quantity} users)"
        else:
            # Для quantity-based: показать % использования
            efficiency = self.get_allocation_percentage()
            return f"Utilization: {efficiency:.1f}%"

class ClientCostDriver(models.Model):
    _name = 'client.cost.driver'
    _description = 'Client Cost Driver Allocation'

    driver_id = fields.Many2one('cost.driver', string='Cost Driver', required=True, ondelete='cascade')
    client_id = fields.Many2one('res.partner', string='Client', required=True,
                                domain=[('is_company', '=', True)])
    quantity = fields.Float(string='Quantity', default=1.0, required=True)

    # ИСПРАВЛЕНО: используем sales_price_per_unit вместо cost_per_unit
    unit_price = fields.Monetary(
        string='Unit Price',
        related='driver_id.sales_price_per_unit',
        store=True,
        readonly=True,
        currency_field='currency_id',
        help='Sales price per unit charged to client (includes markup)'
    )

    # ДОБАВЛЕНО: показываем внутреннюю стоимость для сравнения (только для финансовой группы)
    unit_cost = fields.Monetary(
        string='Unit Cost',
        related='driver_id.cost_per_unit',
        store=True,
        readonly=True,
        currency_field='currency_id',
        groups='cost_allocation.group_cost_allocation_financial',
        help='Internal cost per unit (without markup)'
    )

    allocated_cost = fields.Monetary(
        string='Allocated Cost',
        compute='_compute_allocated_cost',
        store=True,
        currency_field='currency_id',
        help='Total cost allocated to this client (quantity × sales price)'
    )

    # ДОБАВЛЕНО: показываем прибыль от этого клиента
    allocated_profit = fields.Monetary(
        string='Allocated Profit',
        compute='_compute_allocated_profit',
        store=True,
        currency_field='currency_id',
        groups='cost_allocation.group_cost_allocation_financial',
        help='Total profit from this client (quantity × profit per unit)'
    )

    currency_id = fields.Many2one('res.currency', related='driver_id.currency_id', store=True)
    company_id = fields.Many2one('res.company', related='driver_id.company_id', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_allocated_cost(self):
        """ИСПРАВЛЕНО: используем sales price, а не cost price"""
        for record in self:
            record.allocated_cost = record.quantity * record.unit_price

    @api.depends('quantity', 'driver_id.profit_per_unit')
    def _compute_allocated_profit(self):
        """Рассчитать прибыль от этого клиента"""
        for record in self:
            record.allocated_profit = record.quantity * (record.driver_id.profit_per_unit or 0.0)

    @api.constrains('quantity')
    def _check_quantity(self):
        """Проверка количества для quantity-based лицензий"""
        for record in self:
            if record.quantity <= 0:
                raise ValidationError('Quantity must be positive')

            # Для quantity-based лицензий проверяем что не превышаем лимит
            if (record.driver_id.license_type == 'quantity_based' and
                    record.driver_id.total_purchased_quantity > 0):

                # Получаем общее распределенное количество
                total_allocated = record.driver_id.total_allocated_quantity

                # Если это новая запись или количество увеличилось
                if not record._origin or record.quantity > record._origin.quantity:
                    additional_qty = record.quantity - (record._origin.quantity if record._origin else 0)
                    if total_allocated + additional_qty > record.driver_id.total_purchased_quantity:
                        raise ValidationError(
                            f'Cannot allocate {record.quantity} units. '
                            f'Available: {record.driver_id.get_unallocated_quantity()} units'
                        )