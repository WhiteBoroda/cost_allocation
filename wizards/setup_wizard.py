from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ServiceCostingSetupWizard(models.TransientModel):
    _name = 'service.costing.setup.wizard'
    _description = 'Service Costing Setup Wizard'

    company_type = fields.Selection([
        ('it', _('IT Services')),
        ('legal', _('Legal Services')),
        ('accounting', _('Accounting Services')),
        ('financial', _('Financial Consulting')),
        ('construction', _('Construction Services')),
        ('expertise', _('Technical Expertise')),
        ('consulting', _('General Consulting')),
        ('custom', _('Custom Setup'))
    ], string='Business Type', required=True, default='it')

    setup_employees = fields.Boolean(string='Setup Employee Costs', default=True)
    setup_pools = fields.Boolean(string='Setup Cost Pools', default=True)
    setup_drivers = fields.Boolean(string='Setup Cost Drivers', default=True)
    setup_services = fields.Boolean(string='Setup Service Categories', default=True)

    def action_setup_company(self):
        """Setup the company based on selected type"""
        self.ensure_one()
        print("=== WIZARD STARTED ===")
        print(f"Company type: {self.company_type}")
        print(
            f"Setup flags: employees={self.setup_employees}, pools={self.setup_pools}, drivers={self.setup_drivers}, services={self.setup_services}")
        # Проверим права доступа
        if not self.env.user.has_group('cost_allocation.group_cost_allocation_manager'):
            print("ERROR: No permissions!")
            raise ValidationError(_('Only Cost Allocation Managers can run this wizard'))

        try:
            if self.setup_employees:
                print("=== SETTING UP EMPLOYEES ===")
                self._setup_employees()
                print(f"Employees created")

            if self.setup_pools:
                print("=== SETTING UP POOLS ===")
                self._setup_cost_pools()
                print(f"Pools created")

            if self.setup_drivers:
                print("=== SETTING UP DRIVERS ===")
                self._setup_cost_drivers()
                print(f"Drivers created")

            if self.setup_services:
                print("=== SETTING UP SERVICES ===")
                self._setup_service_categories()
                print(f"Services created")

        except Exception as e:
            raise ValidationError(_('Setup failed: %s') % str(e))

        # Show success message and redirect
        return {
            'type': 'ir.actions.act_window',
            'name': _('Setup Complete! ✅ Cost Pools Created'),
            'res_model': 'cost.pool',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'search_default_active': True,
            }
        }

    def _setup_employees(self):
        """Create employee cost records for all employees"""
        employees = self.env['hr.employee'].search([('company_id', '=', self.env.company.id)])
        created_count = 0

        for employee in employees:
            existing = self.env['cost.employee'].search([('employee_id', '=', employee.id)])
            if not existing:
                self.env['cost.employee'].create({
                    'employee_id': employee.id,
                    'monthly_hours': 168.0,
                    'company_id': self.env.company.id,
                })
                created_count += 1

        return created_count

    def _setup_cost_pools(self):
        """Setup cost pools based on company type"""
        pools_data = self._get_pools_data()
        created_count = 0

        for pool_data in pools_data:
            # Добавим company_id и проверим существующие пулы
            pool_data['company_id'] = self.env.company.id
            existing = self.env['cost.pool'].search([
                ('name', '=', pool_data['name']),
                ('company_id', '=', self.env.company.id)
            ])

            if not existing:
                # Создаем пул с правильным code через sequence
                pool = self.env['cost.pool'].create(pool_data)
                created_count += 1

        return created_count

    def _setup_cost_drivers(self):
        """Setup cost drivers based on company type"""
        drivers_data = self._get_drivers_data()
        created_count = 0

        # Получаем созданные пулы текущей компании
        pools = self.env['cost.pool'].search([('company_id', '=', self.env.company.id)])
        pool_mapping = {pool.name: pool.id for pool in pools}

        for driver_data in drivers_data:
            # Добавим company_id
            driver_data['company_id'] = self.env.company.id

            existing = self.env['cost.driver'].search([
                ('name', '=', driver_data['name']),
                ('company_id', '=', self.env.company.id)
            ])

            if not existing:
                # Связываем с пулом если есть mapping
                pool_name = self._get_driver_pool_mapping().get(driver_data['name'])
                if pool_name and pool_name in pool_mapping:
                    driver_data['pool_id'] = pool_mapping[pool_name]

                # Создаем драйвер с правильным code через sequence
                driver = self.env['cost.driver'].create(driver_data)
                created_count += 1

        return created_count

    def _setup_service_categories(self):
        """Setup service categories SAFELY - only for current company"""
        if self.company_type == 'custom':
            return 0

        # ИСПРАВЛЕНО: Работаем только с категориями текущей компании
        current_company_categories = self.env['service.category'].search([
            ('company_id', '=', self.env.company.id)
        ])

        # Деактивируем только категории текущей компании
        if current_company_categories:
            current_company_categories.write({'active': False})

        # Получаем категории для активации
        categories_to_activate = self._get_categories_to_create()
        activated_count = 0

        # Создаем/активируем нужные категории
        for cat_data in categories_to_activate:
            cat_data['company_id'] = self.env.company.id

            existing = self.env['service.category'].search([
                ('name', '=', cat_data['name']),
                ('company_id', '=', self.env.company.id)
            ])

            if existing:
                existing.write({'active': True})
                activated_count += 1
            else:
                # Создаем новую категорию
                self.env['service.category'].create(cat_data)
                activated_count += 1

        return activated_count

    def _get_pools_data(self):
        """Get cost pools data based on company type"""
        pools_mapping = {
            'it': [
                {'name': _('Hardware Support'), 'description': _('Computer equipment and hardware support'),
                 'pool_type': 'indirect'},
                {'name': _('Software Support'), 'description': _('Software and SaaS support'), 'pool_type': 'indirect'},
                {'name': _('Infrastructure'), 'description': _('Network and server infrastructure'),
                 'pool_type': 'indirect'},
                {'name': _('User Support'), 'description': _('End user technical support'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'),
                 'pool_type': 'admin'},
            ],
            'legal': [
                {'name': _('Corporate Law'), 'description': _('Corporate legal services'), 'pool_type': 'indirect'},
                {'name': _('Contract Law'), 'description': _('Contract drafting and review'), 'pool_type': 'indirect'},
                {'name': _('Litigation'), 'description': _('Court proceedings and disputes'), 'pool_type': 'indirect'},
                {'name': _('Compliance'), 'description': _('Legal compliance'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'),
                 'pool_type': 'admin'},
            ],
            'accounting': [
                {'name': _('Bookkeeping'), 'description': _('Daily accounting and bookkeeping'),
                 'pool_type': 'indirect'},
                {'name': _('Tax Services'), 'description': _('Tax preparation and planning'), 'pool_type': 'indirect'},
                {'name': _('Audit'), 'description': _('Audit and assurance services'), 'pool_type': 'indirect'},
                {'name': _('Advisory'), 'description': _('Financial advisory services'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'),
                 'pool_type': 'admin'},
            ],
            'financial': [
                {'name': _('Investment Consulting'), 'description': _('Investment advisory services'),
                 'pool_type': 'indirect'},
                {'name': _('Risk Analysis'), 'description': _('Financial risk assessment'), 'pool_type': 'indirect'},
                {'name': _('Planning'), 'description': _('Financial planning services'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'),
                 'pool_type': 'admin'},
            ],
        }

        return pools_mapping.get(self.company_type, [
            {'name': _('Main Services'), 'description': _('Main operational services'), 'pool_type': 'indirect'},
            {'name': _('Administration'), 'description': _('Administrative and management costs'),
             'pool_type': 'admin'},
        ])

    def _get_drivers_data(self):
        """Get cost drivers data based on company type"""
        drivers_mapping = {
            'it': [
                {'name': _('Workstations'), 'unit_of_measure': 'workstation', 'driver_category': 'Hardware',
                 'unit_name': _('Workstation')},
                {'name': _('Users'), 'unit_of_measure': 'user', 'driver_category': 'User', 'unit_name': _('User')},
                {'name': _('Servers'), 'unit_of_measure': 'server', 'driver_category': 'Infrastructure',
                 'unit_name': _('Server')},
                {'name': _('Applications'), 'unit_of_measure': 'license', 'driver_category': 'Software',
                 'unit_name': _('Application')},
            ],
            'legal': [
                {'name': _('Cases'), 'unit_of_measure': 'unit', 'driver_category': 'Legal', 'unit_name': _('Case')},
                {'name': _('Contracts'), 'unit_of_measure': 'unit', 'driver_category': 'Legal',
                 'unit_name': _('Contract')},
                {'name': _('Work Hours'), 'unit_of_measure': 'hour', 'driver_category': 'Time', 'unit_name': _('Hour')},
            ],
            'accounting': [
                {'name': _('Transactions'), 'unit_of_measure': 'unit', 'driver_category': 'Accounting',
                 'unit_name': _('Transaction')},
                {'name': _('Accounts'), 'unit_of_measure': 'unit', 'driver_category': 'Accounting',
                 'unit_name': _('Account')},
                {'name': _('Reports'), 'unit_of_measure': 'unit', 'driver_category': 'Accounting',
                 'unit_name': _('Report')},
            ],
        }

        return drivers_mapping.get(self.company_type, [
            {'name': _('Main Driver'), 'unit_of_measure': 'Unit', 'driver_category': 'General', 'unit_name': _('Unit')},
        ])

    def _get_driver_pool_mapping(self):
        """Map drivers to pools for linking"""
        mapping = {
            _('Workstations'): _('Hardware Support'),
            _('Users'): _('User Support'),
            _('Servers'): _('Infrastructure'),
            _('Applications'): _('Software Support'),
            _('Cases'): _('Corporate Law'),
            _('Contracts'): _('Contract Law'),
            _('Work Hours'): _('Litigation'),
            _('Transactions'): _('Bookkeeping'),
            _('Accounts'): _('Bookkeeping'),
            _('Reports'): _('Audit'),
        }
        return mapping

    def _get_categories_to_create(self):
        """Get service categories to create/activate based on company type"""
        categories_mapping = {
            'it': [
                {'name': _('IT Hardware'), 'active': True},
                {'name': _('IT Software'), 'active': True},
                {'name': _('IT Infrastructure'), 'active': True},
                {'name': _('IT Support'), 'active': True},
            ],
            'legal': [
                {'name': _('Corporate Law'), 'active': True},
                {'name': _('Contract Law'), 'active': True},
                {'name': _('Litigation'), 'active': True},
            ],
            'accounting': [
                {'name': _('Bookkeeping'), 'active': True},
                {'name': _('Tax Services'), 'active': True},
                {'name': _('Audit'), 'active': True},
            ],
            'financial': [
                {'name': _('Financial Consulting'), 'active': True},
                {'name': _('Investment Advisory'), 'active': True},
            ],
        }

        return categories_mapping.get(self.company_type, [
            {'name': _('Main Services'), 'active': True},
        ])