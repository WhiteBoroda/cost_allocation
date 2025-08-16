from odoo import models, fields, api


class ServiceCostingSetupWizard(models.TransientModel):
    _name = 'service.costing.setup.wizard'
    _description = 'Service Costing Setup Wizard'

    company_type = fields.Selection([
        ('it', 'IT Services'),
        ('legal', 'Legal Services'),
        ('accounting', 'Accounting Services'),
        ('financial', 'Financial Consulting'),
        ('construction', 'Construction Services'),
        ('expertise', 'Technical Expertise'),
        ('consulting', 'General Consulting'),
        ('custom', 'Custom Setup')
    ], string='Business Type', required=True, default='it')

    setup_employees = fields.Boolean(string='Setup Employee Costs', default=True)
    setup_pools = fields.Boolean(string='Setup Cost Pools', default=True)
    setup_drivers = fields.Boolean(string='Setup Cost Drivers', default=True)
    setup_services = fields.Boolean(string='Setup Service Catalog', default=True)

    def action_setup_company(self):
        """Setup the company based on selected type"""
        self.ensure_one()

        if self.setup_employees:
            self._setup_employees()

        if self.setup_pools:
            self._setup_cost_pools()

        if self.setup_drivers:
            self._setup_cost_drivers()

        if self.setup_services:
            self._setup_service_categories()

        # Show success message and redirect to cost pools
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Налаштування завершено!',
                'message': f'Базова конфігурація для {dict(self._fields["company_type"].selection)[self.company_type]} створена. Ви можете редагувати пули затрат та драйвери в меню "Налаштування".',
                'type': 'success',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'Cost Pools',
                    'res_model': 'cost.pool',
                    'view_mode': 'tree,form',
                }
            }
        }

    def _setup_employees(self):
        """Create employee cost records for all employees"""
        employees = self.env['hr.employee'].search([])
        for employee in employees:
            existing = self.env['cost.employee'].search([('employee_id', '=', employee.id)])
            if not existing:
                self.env['cost.employee'].create({
                    'employee_id': employee.id,
                    'monthly_hours': 168.0,
                    'is_diia_city': True,  # Default for Ukrainian companies
                })

    def _setup_cost_pools(self):
        """Setup cost pools based on company type - EDITABLE"""
        pools_data = self._get_pools_data()

        for pool_data in pools_data:
            existing = self.env['cost.pool'].search([('name', '=', pool_data['name'])])
            if not existing:
                # Create pool with description that it can be edited
                pool_data['description'] = f"{pool_data.get('description', '')} (Створено майстром - можна редагувати)"
                self.env['cost.pool'].create(pool_data)

    def _setup_cost_drivers(self):
        """Setup cost drivers based on company type - EDITABLE"""
        drivers_data = self._get_drivers_data()

        # Get created pools to link drivers
        pools = self.env['cost.pool'].search([])
        pool_mapping = {pool.name: pool.id for pool in pools}

        for driver_data in drivers_data:
            existing = self.env['cost.driver'].search([('name', '=', driver_data['name'])])
            if not existing:
                # Try to find matching pool
                pool_name = self._get_driver_pool_mapping().get(driver_data['name'])
                if pool_name and pool_name in pool_mapping:
                    driver_data['pool_id'] = pool_mapping[pool_name]
                    driver_data[
                        'description'] = f"{driver_data.get('description', '')} (Створено майстром - можна редагувати)"
                    self.env['cost.driver'].create(driver_data)

    def _setup_service_categories(self):
        """Activate relevant service categories based on company type"""
        # Get categories to activate
        category_refs = self._get_category_refs()

        # Deactivate all categories first
        all_categories = self.env['service.category'].search([])
        all_categories.write({'active': False})

        # Activate selected categories
        for ref in category_refs:
            try:
                category = self.env.ref(f'cost_allocation.{ref}')
                category.active = True
            except:
                pass  # Category doesn't exist

    def _get_pools_data(self):
        """Get cost pools data based on company type - TEMPLATE DATA"""
        pools_mapping = {
            'it': [
                {'name': 'Підтримка обладнання', 'description': 'Комп\'ютерне обладнання та підтримка заліза',
                 'pool_type': 'indirect'},
                {'name': 'Підтримка ПЗ', 'description': 'Програмне забезпечення та SaaS підтримка',
                 'pool_type': 'indirect'},
                {'name': 'Інфраструктура', 'description': 'Мережева та серверна інфраструктура',
                 'pool_type': 'indirect'},
                {'name': 'Підтримка користувачів', 'description': 'Технічна підтримка кінцевих користувачів',
                 'pool_type': 'indirect'},
                {'name': 'Адміністрування', 'description': 'Адміністративні та управлінські затрати',
                 'pool_type': 'admin'},
            ],
            'legal': [
                {'name': 'Корпоративне право', 'description': 'Корпоративні юридичні послуги', 'pool_type': 'indirect'},
                {'name': 'Договірне право', 'description': 'Складання та перевірка договорів', 'pool_type': 'indirect'},
                {'name': 'Судові процеси', 'description': 'Судові засідання та спори', 'pool_type': 'indirect'},
                {'name': 'Compliance', 'description': 'Юридична відповідність', 'pool_type': 'indirect'},
                {'name': 'Адміністрування', 'description': 'Адміністративні та управлінські затрати',
                 'pool_type': 'admin'},
            ],
            'accounting': [
                {'name': 'Бухгалтерський облік', 'description': 'Щоденний облік та бухгалтерія',
                 'pool_type': 'indirect'},
                {'name': 'Податкові послуги', 'description': 'Підготовка податків та планування',
                 'pool_type': 'indirect'},
                {'name': 'Аудит', 'description': 'Аудиторські та гарантійні послуги', 'pool_type': 'indirect'},
                {'name': 'Консультації', 'description': 'Фінансові консультаційні послуги', 'pool_type': 'indirect'},
                {'name': 'Адміністрування', 'description': 'Адміністративні та управлінські затрати',
                 'pool_type': 'admin'},
            ],
        }

        return pools_mapping.get(self.company_type, [
            {'name': 'Основні послуги', 'description': 'Основні операційні послуги', 'pool_type': 'indirect'},
            {'name': 'Адміністрування', 'description': 'Адміністративні затрати', 'pool_type': 'admin'},
        ])

    def _get_drivers_data(self):
        """Get cost drivers data based on company type"""
        drivers_mapping = {
            'it': [
                {'name': 'Робочі станції', 'code': 'WORKSTATIONS', 'driver_category': 'Hardware', 'unit_name': 'ПК'},
                {'name': 'Користувачі', 'code': 'USERS', 'driver_category': 'Users', 'unit_name': 'Користувач'},
                {'name': 'Сервери', 'code': 'SERVERS', 'driver_category': 'Infrastructure', 'unit_name': 'Сервер'},
                {'name': 'Застосунки', 'code': 'APPS', 'driver_category': 'Software', 'unit_name': 'Застосунок'},
            ],
            'legal': [
                {'name': 'Справи', 'code': 'CASES', 'driver_category': 'Legal', 'unit_name': 'Справа'},
                {'name': 'Договори', 'code': 'CONTRACTS', 'driver_category': 'Legal', 'unit_name': 'Договір'},
                {'name': 'Години роботи', 'code': 'HOURS', 'driver_category': 'Time', 'unit_name': 'Година'},
                {'name': 'Документи', 'code': 'DOCS', 'driver_category': 'Legal', 'unit_name': 'Документ'},
            ],
            'accounting': [
                {'name': 'Транзакції', 'code': 'TRANSACTIONS', 'driver_category': 'Accounting',
                 'unit_name': 'Транзакція'},
                {'name': 'Рахунки', 'code': 'ACCOUNTS', 'driver_category': 'Accounting', 'unit_name': 'Рахунок'},
                {'name': 'Звіти', 'code': 'REPORTS', 'driver_category': 'Accounting', 'unit_name': 'Звіт'},
                {'name': 'Юридичні особи', 'code': 'ENTITIES', 'driver_category': 'Accounting',
                 'unit_name': 'ЮР особа'},
            ],
        }

        return drivers_mapping.get(self.company_type, [
            {'name': 'Основний драйвер', 'code': 'MAIN', 'driver_category': 'General', 'unit_name': 'Одиниця'},
        ])

    def _get_driver_pool_mapping(self):
        """Map drivers to pools for linking"""
        mapping = {
            'Робочі станції': 'Підтримка обладнання',
            'Користувачі': 'Підтримка користувачів',
            'Сервери': 'Інфраструктура',
            'Застосунки': 'Підтримка ПЗ',
            'Справи': 'Корпоративне право',
            'Договори': 'Договірне право',
            'Години роботи': 'Судові процеси',
            'Документи': 'Compliance',
            'Транзакції': 'Бухгалтерський облік',
            'Рахунки': 'Бухгалтерський облік',
            'Звіти': 'Аудит',
            'Юридичні особи': 'Консультації',
        }
        return mapping

    def _get_category_refs(self):
        """Get service category references to activate"""
        category_mapping = {
            'it': ['category_it_hardware', 'category_it_software', 'category_it_infrastructure', 'category_it_support'],
            'legal': ['category_legal_corporate', 'category_legal_contracts', 'category_legal_litigation'],
            'accounting': ['category_accounting_bookkeeping', 'category_accounting_tax', 'category_accounting_audit'],
            'financial': ['category_financial_consulting', 'category_financial_analysis'],
            'construction': ['category_construction_design', 'category_construction_execution'],
            'expertise': ['category_expertise_technical'],
        }

        return category_mapping.get(self.company_type, [])